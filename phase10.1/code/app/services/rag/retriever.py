"""混合检索：Dense 语义检索 + Sparse BM25 关键词 → RRF 融合。

RRF (Reciprocal Rank Fusion) 公式：
    score(d) = Σ 1 / (k + rank_i(d))
    两路分别给出 top_k 结果，按 RRF 分数合并重排。

Sparse 检索用 rank_bm25 库（纯 Python BM25 实现，无重依赖）。
"""

import math
import re
from collections import defaultdict

from app.db import chroma_store
from app.services.rag.embedding import encode_query_coalesced
from app.services.rag.query_cache import (
    get_cached_query_embedding_sync,
    set_cached_query_embedding_sync,
)

# 中文分词简易正则 + 英文分词（BM25 的 tokenizer）
_TOKEN_RE = re.compile(r"[一-鿿]|[a-zA-Z]+|\d+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class BM25Scorer:
    """轻量 BM25 实现（纯 Python，无外部依赖）。"""

    def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs = [_tokenize(d) for d in documents]
        self.n = len(self.docs)
        self.avgdl = sum(len(d) for d in self.docs) / max(self.n, 1)
        self.df: dict[str, int] = defaultdict(int)
        for doc in self.docs:
            for w in set(doc):
                self.df[w] += 1

    def search(self, query: str, top_k: int = 20) -> list[tuple[int, float]]:
        q_tokens = _tokenize(query)
        scores: list[float] = []
        for i, doc in enumerate(self.docs):
            score = 0.0
            dl = len(doc)
            tf: dict[str, int] = defaultdict(int)
            for t in doc:
                tf[t] += 1
            for t in q_tokens:
                f = tf.get(t, 0)
                if f == 0:
                    continue
                df_t = self.df.get(t, 0)
                idf = math.log((self.n - df_t + 0.5) / (df_t + 0.5) + 1.0)
                score += idf * (f * (self.k1 + 1)) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            scores.append(score)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]


def _encode_query_cached(query: str) -> dict:
    """query 向量化（带 Redis 缓存）：同样问题不重复推理 BGE-M3。

    高并发优化：CPU 推理 + GIL 使 embedding 是串行瓶颈，热门问题的向量
    缓存命中后直接复用，跳过推理。
    """
    cached = get_cached_query_embedding_sync(query)
    if cached is not None:
        return {"dense": cached}
    # 攒批推理：并发冷 query 合并为一次批量 encode（100ms 窗口）
    q_vec = encode_query_coalesced(query)
    set_cached_query_embedding_sync(query, q_vec["dense"])
    return q_vec


def hybrid_search(
    kb_id: int,
    query: str,
    dense_top_k: int = 20,
    sparse_top_k: int = 20,
    fusion_k: int = 60,
) -> list[dict]:
    """混合检索：Dense + Sparse → RRF 融合。

    Returns:
        [{"text": str, "metadata": dict, "score": float, "dense_rank": int, "sparse_rank": int}, ...]
    """
    q_vec = _encode_query_cached(query)

    # 1. Dense 检索
    dense_results = chroma_store.search_dense(kb_id, q_vec["dense"], top_k=dense_top_k)
    # dense 相似度按 id 映射（真实余弦相似度，量级 0.3-0.9；RRF 融合分只有 0.01-0.03 不适合展示）
    dense_score_by_id: dict[str, float] = {r["id"]: r.get("score", 0.0) for r in dense_results}

    # 2. Sparse 检索（从 Chroma 拉出全部 chunk 建 BM25）
    #    生产环境中稀疏检索应走独立索引，这里为简化从 Chroma 取全量文本
    all_chunks: list[str] = []
    all_metas: list[dict] = []
    # 收集所有 chunk（一次 query 取全量）
    if dense_results:
        collection = chroma_store.get_or_create_collection(kb_id)
        # 取全量：Chroma 无直接全量导出，用 top_k=10000 近似
        all_data = collection.get(limit=10000, include=["documents", "metadatas"])
        all_chunks = all_data.get("documents", []) or []
        all_metas = all_data.get("metadatas", []) or []
        all_ids = all_data.get("ids", []) or []

    sparse_ranked: list[tuple[int, float]] = []
    if all_chunks:
        bm25 = BM25Scorer(all_chunks)
        sparse_ranked = bm25.search(query, top_k=sparse_top_k)

    # 3. RRF 融合
    rrf: dict[int, float] = defaultdict(float)
    for rank, item in enumerate(dense_results):
        idx = next((j for j, cid in enumerate(all_ids) if cid == item["id"]), -1)
        if idx >= 0:
            rrf[idx] += 1.0 / (fusion_k + rank + 1)
    for rank, (idx, bm25_score) in enumerate(sparse_ranked):
        rrf[idx] += 1.0 / (fusion_k + rank + 1)

    merged = sorted(rrf.items(), key=lambda x: x[1], reverse=True)
    results: list[dict] = []
    for idx, score in merged:
        results.append({
            "text": all_chunks[idx] if idx < len(all_chunks) else "",
            "metadata": all_metas[idx] if idx < len(all_metas) else {},
            "score": round(score, 4),  # RRF 融合分（用于排序）
            "dense_score": dense_score_by_id.get(all_ids[idx] if idx < len(all_ids) else "", 0.0),
            "chunk_id": all_ids[idx] if idx < len(all_ids) else "",
        })
    return results
