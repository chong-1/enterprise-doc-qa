"""Chroma 向量存储：写入 chunk 向量 + 元数据，Dense 语义检索。"""

import logging

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings

logger = logging.getLogger(__name__)

_client = None


def get_chroma_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def _collection_name(kb_id: int) -> str:
    return f"{settings.CHROMA_COLLECTION_PREFIX}{kb_id}"


def get_or_create_collection(kb_id: int) -> chromadb.Collection:
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=_collection_name(kb_id),
        metadata={"kb_id": str(kb_id), "hnsw:space": "cosine"},
    )


def delete_collection(kb_id: int) -> None:
    client = get_chroma_client()
    try:
        client.delete_collection(_collection_name(kb_id))
    except Exception:
        pass


# ===================== Phase 4 新增：写入 & 检索 =====================


def add_chunks(
    kb_id: int,
    chunk_texts: list[str],
    dense_vectors: list[list[float]],
    metadatas: list[dict],
    chunk_ids: list[str],
) -> None:
    """批量写入 chunk（文本 + 向量 + 元数据）到 Chroma。

    Args:
        kb_id: 知识库 ID
        chunk_texts: 分块原文（用于后续展示引用）
        dense_vectors: 每个 chunk 的 1024d 稠密向量
        metadatas: 每个 chunk 的元数据（doc_id, filename, chunk_idx, char_start, char_end）
        chunk_ids: 每个 chunk 的唯一标识（如 "doc_{id}_chunk_{idx}"）
    """
    if not chunk_ids:
        return
    collection = get_or_create_collection(kb_id)
    collection.add(
        ids=chunk_ids,
        documents=chunk_texts,
        embeddings=dense_vectors,
        metadatas=metadatas,
    )
    logger.info(f"Chroma: {kb_id=} 写入 {len(chunk_ids)} chunks")


def search_dense(
    kb_id: int,
    query_vector: list[float],
    top_k: int = 20,
) -> list[dict]:
    """Dense 语义检索：用查询向量搜最相似的 top_k 条 chunk。

    Returns:
        [{"id": str, "text": str, "metadata": dict, "score": float}, ...]
    """
    collection = get_or_create_collection(kb_id)
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    items: list[dict] = []
    if not results["ids"] or not results["ids"][0]:
        return items
    for i, cid in enumerate(results["ids"][0]):
        # cosine distance → similarity (cosine distance ∈ [0, 2], cosine similarity = 1 - distance)
        dist = results["distances"][0][i] if results.get("distances") else 0
        score = 1.0 - dist / 2.0  # 归一化到 [0, 1]
        items.append({
            "id": cid,
            "text": results["documents"][0][i] if results.get("documents") else "",
            "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
            "score": round(score, 4),
        })
    return items


def collection_count(kb_id: int) -> int:
    """返回 Collection 中的 chunk 数量。"""
    return get_or_create_collection(kb_id).count()


def delete_chunks_by_doc(kb_id: int, doc_id: int) -> None:
    """删除指定文档的所有 chunk（通过 metadata 过滤）。

    软删除后调用：Chroma 中该文档的向量立即消失，检索不再命中。
    """
    collection = get_or_create_collection(kb_id)
    # 先取待删 ids（delete 返回 None，无法直接拿删除数）
    matched = collection.get(where={"doc_id": str(doc_id)}, include=[])["ids"]
    if matched:
        collection.delete(ids=matched)
    logger.info(f"Chroma: {kb_id=} 删除文档 {doc_id} 的 {len(matched)} 个 chunk")
