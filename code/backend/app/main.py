"""FastAPI 应用入口。"""

from fastapi import FastAPI

from app.api.v1 import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.middleware import register_middlewares


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。"""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url=f"{settings.API_PREFIX}/docs",
        redoc_url=f"{settings.API_PREFIX}/redoc",
        openapi_url=f"{settings.API_PREFIX}/openapi.json",
    )

    # 注册路由
    app.include_router(api_router, prefix=settings.API_PREFIX)

    # 注册中间件
    register_middlewares(app)

    # 注册异常处理器
    register_exception_handlers(app)

    return app


app = create_app()


# ========== 健康检查（不走 API 前缀） ==========
@app.get("/health", tags=["system"])
async def health_check():
    """健康检查接口。"""
    return {"status": "ok", "version": settings.APP_VERSION}
