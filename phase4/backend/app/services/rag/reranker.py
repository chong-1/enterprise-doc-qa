"""BGE-Reranker-v2-m3 重排序：对检索结果逐条打分，精排 top_k。

模型约 1GB，懒加载全局单例，首次下载到 D:/huggingface。
"""

import os

from app.core.config import settings

_reranker = None


def _init_hf_env() -> None:
    os.environ["HF_ENDPOINT"] = settings.HF_ENDPOINT
    if settings.HF_HOME:
        os.environ["HF_HOME"] = settings.HF_HOME


def get_reranker():
    global _reranker
    if _reranker is None:
        _init_hf_env()
        from FlagEmbedding import FlagReranker

        _reranker = FlagReranker(
            settings.RERANKER_MODEL,
            use_fp16=False,
            device=settings.RERANKER_DEVICE,
        )
    return _reranker


def rerank(
    query: str,
    candidates: list[dict],
    top_k: int | None = None,
) -> list[dict]:
    """对检索候选结果用 Reranker 精排。

    Args:
        query: 用户问题
        candidates: 检索粗筛结果列表，每项含 "text" 字段
        top_k: 精排后保留的数量，默认取配置 RERANKER_TOP_K

    Returns:
        原有 candidates 加上了 "rerank_score" 字段，按分降序，取 top_k
    """
    if not candidates:
        return []

    top_k = top_k or settings.RERANKER_TOP_K
    model = get_reranker()
    pairs = [[query, c["text"]] for c in candidates]
    scores = model.compute_score(pairs)

    # compute_score 可能返回单 float 或列表
    if not isinstance(scores, list):
        scores = [scores]

    for i, s in enumerate(scores):
        candidates[i]["rerank_score"] = round(float(s), 4)

    candidates.sort(key=lambda c: c.get("rerank_score", 0), reverse=True)
    return candidates[:top_k]
