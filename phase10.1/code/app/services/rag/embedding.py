"""BGE-M3 Embedding 服务：Dense 1024d + Sparse 词汇权重，一次调用同时生成。

BGEM3FlagModel 是 BGE-M3 的官方封装，单次 encode 同时返回 dense 和 sparse，
避免分别加载 SentenceTransformer 和 FlagEmbedding 导致模型在内存中存两份（~4.4GB）。

高并发优化：encode_query_coalesced 提供"请求合并"（攒批）——100ms 窗口内
并发到达的 query 合并为一次批量推理（batch 推理比 N 次单条推理总耗时少 2-5 倍），
PyTorch CPU 算子推理时会释放 GIL，后台线程批量推理期间 API 事件循环不被完全阻塞。
"""

import logging
import os
import threading
import time

from app.core.config import settings

logger = logging.getLogger(__name__)

_model = None

# ========== 攒批（请求合并） ==========
# 设计：线程安全队列 + 后台 flush 线程。请求进入窗口后等待，窗口到期或被
# 填满时批量推理一次，结果按序发回。队列空闲超窗口后线程自动退出，下次请求重新拉起。
_BATCH_WINDOW = 0.1          # 攒批窗口（秒）：请求最多等待 100ms 参与合并
_BATCH_MAX_SIZE = 32         # 单批最大条数：达到立即 flush，防止窗口期无限膨胀
_BATCH_WAIT_TIMEOUT = 10.0   # 等待结果兜底超时（秒），防线程异常导致永久挂起

_batch_lock = threading.Lock()
_pending: list[tuple[str, threading.Event, list]] = []  # (text, event, [result])
_flush_thread: threading.Thread | None = None


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


# ========== 攒批推理（请求合并） ==========


def _flush_batch() -> None:
    """把当前窗口内累积的 query 合并为一次批量推理，结果按序发回。"""
    with _batch_lock:
        batch = _pending[:]
        _pending.clear()
    if not batch:
        return
    texts = [t for t, _, _ in batch]
    try:
        results = encode(texts)
        for (_, ev, slot), res in zip(batch, results):
            slot.append(res)
            ev.set()
        logger.info(f"embedding 攒批推理: {len(batch)} 条合并为 1 次")
    except Exception as exc:
        logger.error(f"embedding 批量推理失败: {exc}")
        for _, ev, slot in batch:
            slot.append({"error": str(exc)})
            ev.set()


def _batch_loop() -> None:
    """后台 flush 线程：窗口到期 flush 一次，队列空闲则退出。"""
    while True:
        time.sleep(_BATCH_WINDOW)
        with _batch_lock:
            if not _pending:
                return  # 空闲退出，下个请求重新拉起线程
        _flush_batch()


def encode_query_coalesced(text: str) -> dict:
    """带攒批的 query 向量化：100ms 窗口内并发请求合并为一次批量推理。

    同步接口（调用方无感知），失败时兜底直接单条推理，保证可用性。
    """
    global _flush_thread
    ev = threading.Event()
    slot: list = []

    with _batch_lock:
        _pending.append((text, ev, slot))
        size = len(_pending)
        need_start = _flush_thread is None or not _flush_thread.is_alive()
    if size >= _BATCH_MAX_SIZE:
        _flush_batch()  # 达到批容量立即 flush（锁已释放）
    elif need_start:
        _flush_thread = threading.Thread(target=_batch_loop, daemon=True)
        _flush_thread.start()

    if not ev.wait(timeout=_BATCH_WAIT_TIMEOUT):
        # 兜底：线程异常/超时，直接单条推理（牺牲合并收益换可用性）
        logger.warning("embedding 攒批等待超时，回退单条推理")
        with _batch_lock:
            try:
                _pending.remove((text, ev, slot))
            except ValueError:
                pass
        return encode_query(text)

    result = slot[0] if slot else {}
    if "error" in result:
        raise RuntimeError(result["error"])
    return result
