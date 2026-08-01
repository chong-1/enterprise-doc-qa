"""Chroma 向量存储封装。

Chroma 使用同步 API（暂不支持原生 async），实际调用时应在 run_in_executor 中执行。
"""

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings

_chroma_client: chromadb.PersistentClient | None = None


def get_chroma_client() -> chromadb.PersistentClient:
    """获取 Chroma 客户端（懒加载单例）。"""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _chroma_client


def get_or_create_collection(
    kb_id: int,
) -> chromadb.Collection:
    """获取或创建知识库对应的 Collection。"""
    client = get_chroma_client()
    collection_name = f"{settings.CHROMA_COLLECTION_PREFIX}{kb_id}"
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"kb_id": str(kb_id), "hnsw:space": "cosine"},
    )


def delete_collection(kb_id: int) -> None:
    """删除知识库对应的 Collection。"""
    client = get_chroma_client()
    collection_name = f"{settings.CHROMA_COLLECTION_PREFIX}{kb_id}"
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass  # Collection 不存在则忽略
