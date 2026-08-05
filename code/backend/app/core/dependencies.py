"""FastAPI 依赖注入：数据库会话、当前用户、权限校验。"""

from typing import Annotated, Callable

from fastapi import Depends, Header, Path
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import NotFoundError, PermissionDeniedError, UnauthorizedError
from app.core.security import decode_token
from app.db.session import async_session_factory
from app.models.knowledge_base import KBMemberRole, KnowledgeBase, KnowledgeBaseMember
from app.models.user import Role, User

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


async def get_current_user(
    user_id: Annotated[int, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """加载当前登录用户的完整信息（含角色、权限）。"""
    stmt = (
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .where(User.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise UnauthorizedError("用户不存在或已被禁用")
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    """管理员校验：要求 is_superuser。"""

    if not user.is_superuser:
        raise PermissionDeniedError("需要管理员权限")
    return user


# ========== 知识库级权限（Phase 7） ==========

#: 角色层级：viewer(1) < editor(2) < owner(3)
_ROLE_LEVEL = {KBMemberRole.VIEWER: 1, KBMemberRole.EDITOR: 2, KBMemberRole.OWNER: 3}


async def check_kb_access(db: AsyncSession, user: User, kb_id: int, min_role: str) -> None:
    """校验用户对知识库的最小角色权限，不满足抛 PermissionDeniedError。

    - 超管 / owner 恒通过
    - 公开知识库 = 全员 viewer
    - 否则查 kb_members 表
    """
    if user.is_superuser:
        return
    min_level = _ROLE_LEVEL[KBMemberRole(min_role)]

    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise NotFoundError(f"知识库 {kb_id} 不存在")
    if kb.owner_id == user.id:
        return
    if kb.is_public and min_level <= _ROLE_LEVEL[KBMemberRole.VIEWER]:
        return

    stmt = select(KnowledgeBaseMember).where(
        KnowledgeBaseMember.kb_id == kb_id, KnowledgeBaseMember.user_id == user.id
    )
    result = await db.execute(stmt)
    member = result.scalar_one_or_none()
    if member and _ROLE_LEVEL[member.role] >= min_level:
        return
    raise PermissionDeniedError(f"无权限访问知识库 {kb_id}")


def require_kb_role(min_role: str = "viewer") -> Callable:
    """知识库角色校验依赖工厂（kb_id 来自路径参数）。

    用法：
        @router.post("/{kb_id}/upload")
        async def upload(
            _, kb_id: int, user: Annotated[User, Depends(require_kb_role("editor"))]
        ):
            ...
    """

    async def _checker(
        kb_id: int = Path(...),
        db: Annotated[AsyncSession, Depends(get_db)] = None,
        user: Annotated[User, Depends(get_current_user)] = None,
    ) -> User:
        await check_kb_access(db, user, kb_id, min_role)
        return user

    return _checker


# ========== 类型别名（方便端点签名） ==========
DB = Annotated[AsyncSession, Depends(get_db)]
CurrentUserId = Annotated[int, Depends(get_current_user_id)]
CurrentUser = Annotated[User, Depends(get_current_user)]
