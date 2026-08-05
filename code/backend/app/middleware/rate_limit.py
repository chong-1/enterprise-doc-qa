"""基于 Redis 的接口限流中间件。

限流键：登录用户用 user_id，匿名用 IP；按分钟窗口计数。
- 开关：RATE_LIMIT_ENABLED（默认关闭，验证时手动开启）
- 上限：RATE_LIMIT_PER_MINUTE（每分钟请求数）
- 认证接口 / 文档页不做限流（避免误伤登录）
- Redis 不可用时 fail-open（不影响主流程）
"""

import time

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.security import decode_token
from app.db.redis_client import get_redis

#: 不做限流的路径前缀
_SKIP_PREFIXES = (
    "/health",
    "/api/v1/docs",
    "/api/v1/redoc",
    "/api/v1/openapi.json",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
)


def _identity_key(request: Request) -> str:
    """计算限流身份键：优先 user_id，匿名用 IP。"""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        payload = decode_token(auth[7:])
        if payload:
            return f"user:{payload.get('sub', '')}"
    fwd = request.headers.get("x-forwarded-for")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")
    return f"ip:{ip}"


class RateLimitMiddleware:
    """ASGI 中间件：Redis INCR + 60s 窗口，超限返回 429。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not settings.RATE_LIMIT_ENABLED:
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        if request.url.path.startswith(_SKIP_PREFIXES):
            await self.app(scope, receive, send)
            return

        bucket = int(time.time() // 60)
        key = f"rate_limit:{_identity_key(request)}:{bucket}"
        try:
            redis = await get_redis()
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, 120)
            if count > settings.RATE_LIMIT_PER_MINUTE:
                response = JSONResponse(
                    status_code=429,
                    content={"code": 429, "message": "请求过于频繁，请稍后再试", "data": None},
                )
                await response(scope, receive, send)
                return
        except Exception:
            pass  # Redis 不可用 → 不限流

        await self.app(scope, receive, send)
