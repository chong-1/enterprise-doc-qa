"""审计日志查询 API（仅管理员）。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.core.dependencies import DB, require_admin
from app.core.exceptions import paginated_response
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogResponse

router = APIRouter()


@router.get("", summary="审计日志列表（管理员）")
async def list_audit_logs(
    db: DB,
    _: Annotated[User, Depends(require_admin)],
    page: int = 1,
    page_size: int = 20,
    user_id: int | None = None,
    action: str | None = None,
    resource_type: str | None = None,
):
    """分页查询审计日志，支持按操作人/操作类型/资源类型过滤（仅管理员）。"""
    stmt = select(AuditLog, User.username).outerjoin(User, AuditLog.user_id == User.id)
    count_stmt = select(func.count()).select_from(AuditLog)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
        count_stmt = count_stmt.where(AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
        count_stmt = count_stmt.where(AuditLog.resource_type == resource_type)

    total = (await db.execute(count_stmt)).scalar() or 0
    result = await db.execute(
        stmt.order_by(AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        AuditLogResponse(
            id=log.id, user_id=log.user_id, username=username,
            action=log.action, resource_type=log.resource_type,
            resource_id=log.resource_id, detail=log.detail,
            ip_address=log.ip_address, created_at=log.created_at,
        )
        for log, username in result.all()
    ]
    return paginated_response(items, total, page, page_size)
