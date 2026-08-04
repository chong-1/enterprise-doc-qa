"""中间件注册。"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.middleware.rate_limit import RateLimitMiddleware


def register_middlewares(app: FastAPI) -> None:
    """注册全局中间件。"""

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 限流（Phase 7）：Redis + ip/user_id 双键，RATE_LIMIT_ENABLED 开关
    app.add_middleware(RateLimitMiddleware)
