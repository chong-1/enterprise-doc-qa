"""FastAPI 依赖注入：数据库会话、当前用户等。"""

from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_token
from app.db.session import async_session_factory

# HTTP Bearer Token 提取器
security_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncSession:
    """获取数据库异步会话（FastAPI Depends）。"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    authorization: str | None = Header(default=None),
) -> str | None:
    """从 Authorization header 提取 Bearer token，绕过未传时报 403 的问题。"""
    if credentials:
        return credentials.credentials
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return None


async def get_current_user_id(token: Annotated[str | None, Depends(get_token)]) -> int:
    """从 JWT 中解析当前用户 ID。未登录抛出 UnauthorizedError。"""
    if not token:
        raise UnauthorizedError("请先登录")

    payload = decode_token(token)
    if payload is None:
        raise UnauthorizedError("Token 无效或已过期")

    if payload.get("type") != "access":
        raise UnauthorizedError("请使用 Access Token")

    try:
        return int(payload["sub"])
    except (ValueError, KeyError):
        raise UnauthorizedError("Token 格式错误")


# ========== 类型别名（方便端点签名） ==========
DB = Annotated[AsyncSession, Depends(get_db)]
CurrentUserId = Annotated[int, Depends(get_current_user_id)]
