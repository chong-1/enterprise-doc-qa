"""文档相关 Schema。"""

from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    """文档响应。"""

    id: int
    kb_id: int
    filename: str
    file_type: str
    file_size: int
    storage_path: str = ""
    chunk_count: int = 0
    status: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentStatusResponse(BaseModel):
    """文档处理状态响应。"""

    id: int
    filename: str
    status: str
    chunk_count: int
    error_message: str | None
