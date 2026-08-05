"""用户管理 API（Phase 7：管理员后台——列表/禁用/角色分配）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, or_
from sqlalchemy.orm import selectinload

from app.core.dependencies import CurrentUser, DB, require_admin
from app.core.exceptions import BadRequestError, NotFoundError, success_response, paginated_response
from app.models.user import Permission, Role, User
from app.schemas.user import UserResponse
from app.services import audit_service
from app.services.audit_service import client_ip

router = APIRouter()


class UserUpdateAdmin(BaseModel):
    """管理员更新用户请求。"""

    is_active: bool | None = None
    is_superuser: bool | None = None
    role_codes: list[str] | None = Field(default=None, description="角色编码列表")


class RoleResponse(BaseModel):
    """角色响应（含权限编码）。"""

    id: int
    name: str
    code: str
    description: str | None
    permissions: list[str] = []


@router.get("/me", summary="获取当前登录用户信息")
async def get_current_user_info(user: CurrentUser) -> dict:
    """返回当前用户信息（含角色列表）。"""
    return success_response(UserResponse.from_user(user))


@router.get("", summary="用户列表（管理员）")
async def list_users(
    db: DB,
    _: Annotated[User, Depends(require_admin)],
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
):
    """分页列出全部用户，可按用户名/邮箱搜索（仅管理员）。"""
    stmt = select(User)
    count_stmt = select(func.count()).select_from(User)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(User.username.like(like), User.email.like(like)))
        count_stmt = count_stmt.where(or_(User.username.like(like), User.email.like(like)))

    total = (await db.execute(count_stmt)).scalar() or 0
    result = await db.execute(
        stmt.options(selectinload(User.roles))
        .order_by(User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    users = [UserResponse.from_user(u) for u in result.scalars().all()]
    return paginated_response(users, total, page, page_size)


@router.get("/roles", summary="角色列表（管理员）")
async def list_roles(
    db: DB,
    _: Annotated[User, Depends(require_admin)],
):
    """列出全部角色及其权限（仅管理员）。"""
    result = await db.execute(
        select(Role).options(selectinload(Role.permissions)).order_by(Role.id)
    )
    roles = [
        RoleResponse(
            id=r.id, name=r.name, code=r.code, description=r.description,
            permissions=[p.code for p in r.permissions],
        )
        for r in result.scalars().all()
    ]
    return success_response(roles)


@router.patch("/{user_id}", summary="更新用户（管理员）")
async def update_user(
    user_id: int,
    body: UserUpdateAdmin,
    db: DB,
    admin: CurrentUser,
    request: Request,
    _: Annotated[User, Depends(require_admin)],
):
    """禁用/启用用户、分配角色、设置超管（仅管理员）。

    注意：不允许管理员禁用自己（防止锁死系统）。
    """
    target = await db.get(User, user_id, options=[selectinload(User.roles)])
    if target is None:
        raise NotFoundError(f"用户 {user_id} 不存在")
    if user_id == admin.id and body.is_active is False:
        raise BadRequestError("不能禁用自己")

    changes: dict = {}
    if body.is_active is not None and body.is_active != target.is_active:
        target.is_active = body.is_active
        changes["is_active"] = body.is_active
    if body.is_superuser is not None and body.is_superuser != target.is_superuser:
        target.is_superuser = body.is_superuser
        changes["is_superuser"] = body.is_superuser

    if body.role_codes is not None:
        role_result = await db.execute(
            select(Role).where(Role.code.in_(body.role_codes))
        )
        target.roles = list(role_result.scalars().all())
        changes["roles"] = body.role_codes

    await audit_service.log_action(
        db, admin, "user:update", "user", user_id,
        {"target": target.username, "changes": changes},
        client_ip(request),
    )
    return success_response(UserResponse.from_user(target), message="用户已更新")
