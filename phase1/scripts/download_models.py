"""预下载 Embedding 和 Reranker 模型。

首次运行前执行，避免启动时长时间等待。

使用方法：
    python scripts/download_models.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.config import settings


def download_embedding_model():
    """下载 BGE-M3 Embedding 模型（~2GB）。"""
    print(f"[1/2] 下载 Embedding 模型: {settings.EMBEDDING_MODEL} ...")
    from sentence_transformers import SentenceTransformer

    SentenceTransformer(settings.EMBEDDING_MODEL, device="cpu")
    print(f"  [OK] {settings.EMBEDDING_MODEL} 下载完成")


def download_reranker_model():
    """下载 BGE-Reranker 模型（~1GB）。"""
    print(f"[2/2] 下载 Reranker 模型: {settings.RERANKER_MODEL} ...")
    from FlagEmbedding import FlagReranker

    FlagReranker(settings.RERANKER_MODEL, use_fp16=False)
    print(f"  [OK] {settings.RERANKER_MODEL} 下载完成")


if __name__ == "__main__":
    print("开始下载模型（首次运行耗时较长，请耐心等待）...")
    print(f"Embedding 模型: {settings.EMBEDDING_MODEL}")
    print(f"Reranker 模型: {settings.RERANKER_MODEL}")
    print(f"设备: {settings.EMBEDDING_DEVICE}")
    print("-" * 50)

    download_embedding_model()
    download_reranker_model()

    print("-" * 50)
    print("全部模型下载完成！")
    print(f"模型缓存路径: ~/.cache/huggingface/")
