"""通用 Schema：分页、统一响应。"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """分页请求参数。"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应。"""

    items: list[T]
    total: int
    page: int
    page_size: int


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应。"""

    code: int = 200
    message: str = "success"
    data: T | None = None
