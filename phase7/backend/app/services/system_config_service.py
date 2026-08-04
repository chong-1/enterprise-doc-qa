"""系统配置服务：键值对存储 + TTL 内存缓存。

LLM 参数等高频读取的配置走缓存（默认 30s），修改后立即失效。
"""

import time
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_config import SystemConfig

_cache: dict[str, tuple[float, str | None]] = {}
CACHE_TTL_SECONDS = 30


async def get_config(db: AsyncSession, key: str, default: str | None = None) -> str | None:
    """读取配置值；不存在或已过期时查库。"""
    now = time.monotonic()
    cached = _cache.get(key)
    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        return cached[1] if cached[1] is not None else default

    stmt = select(SystemConfig).where(SystemConfig.key == key)
    result = await db.execute(stmt)
    cfg = result.scalar_one_or_none()
    value = cfg.value if cfg else None
    _cache[key] = (now, value)
    return value if value is not None else default


async def get_int_config(db: AsyncSession, key: str, default: int) -> int:
    """读取整型配置，解析失败回退默认值。"""
    raw = await get_config(db, key, str(default))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


async def get_float_config(db: AsyncSession, key: str, default: float) -> float:
    """读取浮点型配置，解析失败回退默认值。"""
    raw = await get_config(db, key, str(default))
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


async def set_config(
    db: AsyncSession,
    key: str,
    value: str,
    description: str | None = None,
) -> SystemConfig:
    """写入配置（不存在则创建），并失效缓存。"""
    stmt = select(SystemConfig).where(SystemConfig.key == key)
    result = await db.execute(stmt)
    cfg = result.scalar_one_or_none()
    if cfg is None:
        cfg = SystemConfig(key=key, value=value, description=description)
        db.add(cfg)
    else:
        cfg.value = value
        if description is not None:
            cfg.description = description
    cfg.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _cache.pop(key, None)
    await db.flush()
    return cfg


async def list_configs(db: AsyncSession) -> list[SystemConfig]:
    """列出全部配置（按 id 排序）。"""
    result = await db.execute(select(SystemConfig).order_by(SystemConfig.id))
    return list(result.scalars().all())
