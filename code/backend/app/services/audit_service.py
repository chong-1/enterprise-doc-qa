"""操作审计日志服务：所有关键操作（上传/删除/问答/权限变更）入库。"""

import json
from datetime import datetime

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User


def client_ip(request: Request) -> str:
    """提取客户端 IP（考虑反向代理头 x-forwarded-for）。"""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def log_action(
    db: AsyncSession,
    user: User | None,
    action: str,
    resource_type: str,
    resource_id: int | None = None,
    detail: dict | str | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """记录一条审计日志（调用方负责 commit）。

    Args:
        action: 操作类型，如 kb:create / document:delete / qa:query
        resource_type: 资源类型，如 kb / document / user / qa
        detail: 附加信息（dict 自动序列化为 JSON）
    """
    entry = AuditLog(
        user_id=user.id if user else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=json.dumps(detail, ensure_ascii=False) if isinstance(detail, dict) else detail,
        ip_address=ip_address,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    db.add(entry)
    await db.flush()
    return entry
