"""问答缓存层：答案缓存 + query 向量缓存 + 缓存失效。

高并发优化（削峰三板斧）：
1. 答案缓存：热门重复问题命中后直接返回，跳过 embedding 推理和 LLM API 调用
   （一次问答从"5s + 1 次 API"变成"1ms + 0 次 API"）
2. query 向量缓存：同样问题不重复推理 BGE-M3（GIL 下 CPU 推理是串行瓶颈）
3. 知识库更新时清空该 KB 的答案缓存，防止答案过时（文档变了答案必须跟着变）

提供 async + sync 双接口：
- async 版供 FastAPI 层（pipeline / api）使用
- sync 版供 Celery 任务和同步检索链路（retriever.hybrid_search）使用
"""

import hashlib
import json
import re

from app.core.config import settings
from app.db.redis_client import get_redis

# 规范化：压缩空白 + 去标点，让相似问法（"年假几天"vs"年假有几天？"）命中同一缓存
_PUNCT_RE = re.compile(r"[\s　，。！？、；：""''（）【】《》,.!?;:'\"()\[\]<>/\\-]+")

_ANS_KEY = "qa:ans:{kb_id}:{qhash}"   # 答案缓存
_EMB_KEY = "qa:qemb:{qhash}"          # query 向量缓存

_sync_redis = None


# ========== 问题规范化 ==========


def normalize_question(question: str) -> str:
    """规范化问题：去空白/标点、全角转半角、统一小写。"""
    q = question.strip()
    q = q.translate(str.maketrans("，。！？；：（）【】《》", ",.!?;:()[]<>"))
    q = _PUNCT_RE.sub("", q)
    return q.lower()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ========== 同步 Redis 客户端（Celery / 同步检索用） ==========


def _get_sync_redis():
    """懒加载同步 Redis 客户端（仅缓存层使用，连接数极少）。"""
    global _sync_redis
    if _sync_redis is None:
        import redis
        _sync_redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _sync_redis


# ========== 答案缓存（async） ==========


async def get_cached_answer(kb_id: int, question: str) -> dict | None:
    """取缓存答案。返回 {"answer", "citations", "from_cache"} 或 None。"""
    if not settings.QA_CACHE_ENABLED:
        return None
    r = await get_redis()
    raw = await r.get(_ANS_KEY.format(kb_id=kb_id, qhash=_hash(normalize_question(question))))
    if not raw:
        return None
    try:
        data = json.loads(raw)
        data["from_cache"] = True
        return data
    except Exception:
        return None


async def set_cached_answer(kb_id: int, question: str, answer: str, citations: list[dict]) -> None:
    """写缓存答案（含引用），TTL 后自动过期。"""
    if not settings.QA_CACHE_ENABLED:
        return
    r = await get_redis()
    payload = json.dumps({"answer": answer, "citations": citations}, ensure_ascii=False)
    await r.set(
        _ANS_KEY.format(kb_id=kb_id, qhash=_hash(normalize_question(question))),
        payload,
        ex=settings.QA_CACHE_TTL,
    )


# ========== query 向量缓存（async + sync） ==========


async def get_cached_query_embedding(text: str) -> list[float] | None:
    r = await get_redis()
    raw = await r.get(_EMB_KEY.format(qhash=_hash(normalize_question(text))))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


async def set_cached_query_embedding(text: str, vector: list[float]) -> None:
    r = await get_redis()
    await r.set(
        _EMB_KEY.format(qhash=_hash(normalize_question(text))),
        json.dumps(vector),
        ex=settings.QUERY_EMB_CACHE_TTL,
    )


def get_cached_query_embedding_sync(text: str) -> list[float] | None:
    """同步版（retriever.hybrid_search 在同步代码路径中使用）。"""
    raw = _get_sync_redis().get(_EMB_KEY.format(qhash=_hash(normalize_question(text))))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def set_cached_query_embedding_sync(text: str, vector: list[float]) -> None:
    _get_sync_redis().set(
        _EMB_KEY.format(qhash=_hash(normalize_question(text))),
        json.dumps(vector),
        ex=settings.QUERY_EMB_CACHE_TTL,
    )


# ========== 缓存失效 ==========


async def clear_kb_cache(kb_id: int) -> None:
    """知识库更新（文档增删/重向量化）时清空该 KB 的答案缓存，防答案过时。"""
    if not settings.QA_CACHE_ENABLED:
        return
    r = await get_redis()
    pattern = f"qa:ans:{kb_id}:*"
    async for key in r.scan_iter(match=pattern, count=100):
        await r.delete(key)


def clear_kb_cache_sync(kb_id: int) -> None:
    """同步版（Celery 文档处理任务完成后调用）。"""
    if not settings.QA_CACHE_ENABLED:
        return
    r = _get_sync_redis()
    for key in r.scan_iter(match=f"qa:ans:{kb_id}:*", count=100):
        r.delete(key)
