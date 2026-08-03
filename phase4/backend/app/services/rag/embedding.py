"""BGE-M3 Embedding 服务：Dense 1024d + Sparse 词汇权重，一次调用同时生成。

BGEM3FlagModel 是 BGE-M3 的官方封装，单次 encode 同时返回 dense 和 sparse，
避免分别加载 SentenceTransformer 和 FlagEmbedding 导致模型在内存中存两份（~4.4GB）。
"""

import os

from app.core.config import settings

_model = None


def _init_hf_env() -> None:
    os.environ["HF_ENDPOINT"] = settings.HF_ENDPOINT
    if settings.HF_HOME:
        os.environ["HF_HOME"] = settings.HF_HOME


def get_model():
    """懒加载 BGE-M3（全局单例，~2.2GB，首次下载走 D:/huggingface）。"""
    global _model
    if _model is None:
        _init_hf_env()
        from FlagEmbedding import BGEM3FlagModel

        _model = BGEM3FlagModel(
            settings.EMBEDDING_MODEL,
            use_fp16=False,
            device=settings.EMBEDDING_DEVICE,
        )
    return _model


def encode(
    texts: list[str],
    batch_size: int | None = None,
) -> list[dict]:
    """对一批文本生成 dense + sparse 向量。

    Returns:
        [{"dense": [1024 floats], "sparse": {token_id: weight}}, ...]
    """
    bs = batch_size or settings.EMBEDDING_BATCH_SIZE
    model = get_model()
    outputs = model.encode(
        texts,
        batch_size=bs,
        return_dense=True,
        return_sparse=True,
    )
    results: list[dict] = []
    dense_all = outputs["dense_vecs"]
    sparse_all = outputs["lexical_weights"]
    for i in range(len(texts)):
        sv = sparse_all[i]
        if not isinstance(sv, dict):
            sv = {int(k): float(v) for k, v in sv.items()}
        results.append({
            "dense": dense_all[i].tolist(),
            "sparse": {int(k): float(v) for k, v in sv.items()},
        })
    return results


def encode_query(text: str) -> dict:
    """对单个查询文本生成向量（便捷方法）。"""
    return encode([text])[0]
