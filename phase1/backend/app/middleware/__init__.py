"""中间件注册。"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


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

    # TODO: Phase 2 添加请求日志中间件
    # TODO: Phase 2 添加限流中间件
