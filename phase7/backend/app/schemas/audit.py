"""审计日志 Schema。"""

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    """审计日志响应（含操作人用户名）。"""

    id: int
    user_id: int | None
    username: str | None = None
    action: str
    resource_type: str
    resource_id: int | None
    detail: str | None
    ip_address: str | None
    created_at: str
