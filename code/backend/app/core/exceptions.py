"""自定义异常类和全局异常处理器。"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger


# ========== 自定义业务异常 ==========
class AppException(Exception):
    """业务异常基类。"""

    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(AppException):
    """资源不存在 (404)。"""

    def __init__(self, message: str = "资源不存在"):
        super().__init__(message, code=404)


class PermissionDeniedError(AppException):
    """权限不足 (403)。"""

    def __init__(self, message: str = "权限不足"):
        super().__init__(message, code=403)


class UnauthorizedError(AppException):
    """未认证 (401)。"""

    def __init__(self, message: str = "请先登录"):
        super().__init__(message, code=401)


class BadRequestError(AppException):
    """请求参数错误 (400)。"""

    def __init__(self, message: str = "请求参数有误"):
        super().__init__(message, code=400)


class ConflictError(AppException):
    """资源冲突 (409)。"""

    def __init__(self, message: str = "资源已存在"):
        super().__init__(message, code=409)


class ServiceError(AppException):
    """服务内部错误 (500)。"""

    def __init__(self, message: str = "服务内部错误"):
        super().__init__(message, code=500)


# ========== 统一响应格式 ==========
def success_response(data=None, message: str = "success") -> dict:
    """构建成功响应。"""
    return {
        "code": 200,
        "message": message,
        "data": data,
    }


def paginated_response(
    items: list, total: int, page: int, page_size: int
) -> dict:
    """构建分页响应。"""
    return {
        "code": 200,
        "message": "success",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


# ========== 注册全局异常处理器 ==========
def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器到 FastAPI app。"""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        logger.warning(f"[{exc.code}] {exc.message} | {request.method} {request.url.path}")
        return JSONResponse(
            status_code=exc.code if exc.code < 500 else 500,
            content={"code": exc.code, "message": exc.message, "data": None},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception(f"未处理的异常: {exc} | {request.method} {request.url.path}")
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": "服务器内部错误", "data": None},
        )
