"""知识库 CRUD + 成员管理 API（Phase 7：多知识库隔离 + 角色权限）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.core.dependencies import DB, CurrentUser, require_kb_role
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError, success_response
from app.models.knowledge_base import KBMemberRole, KnowledgeBase, KnowledgeBaseMember
from app.models.user import User
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseResponse, KnowledgeBaseUpdate
from app.schemas.member import KBMemberCreate, KBMemberResponse, KBMemberUpdate
from app.services import audit_service
from app.services.audit_service import client_ip
from app.services.document.loader import delete_file

router = APIRouter()


def _to_response(kb: KnowledgeBase, my_role: str = "viewer") -> KnowledgeBaseResponse:
    """ORM → 响应（补 document_count，排除软删除文档）。"""
    resp = KnowledgeBaseResponse.model_validate(kb)
    resp.document_count = len([d for d in kb.documents if not d.is_deleted])
    resp.my_role = my_role
    return resp


async def _get_kb(db, kb_id: int) -> KnowledgeBase:
    """加载知识库（含成员），不存在抛 404。"""
    stmt = (
        select(KnowledgeBase)
        .options(selectinload(KnowledgeBase.documents))
        .where(KnowledgeBase.id == kb_id)
    )
    result = await db.execute(stmt)
    kb = result.scalar_one_or_none()
    if kb is None:
        raise NotFoundError(f"知识库 {kb_id} 不存在")
    return kb


async def _load_member_roles(db, user_id: int) -> dict[int, str]:
    """加载用户所有知识库成员角色：{kb_id: role}。"""
    result = await db.execute(
        select(KnowledgeBaseMember).where(KnowledgeBaseMember.user_id == user_id)
    )
    return {m.kb_id: m.role.value for m in result.scalars().all()}


@router.post("")
async def create_knowledge_base(
    body: KnowledgeBaseCreate,
    db: DB,
    user: CurrentUser,
    request: Request,
):
    """创建知识库（创建者自动成为 owner）。"""
    kb = KnowledgeBase(
        name=body.name,
        description=body.description,
        owner_id=user.id,
        embedding_model=body.embedding_model,
        chunk_size=body.chunk_size,
        chunk_overlap=body.chunk_overlap,
        is_public=body.is_public,
    )
    db.add(kb)
    await db.flush()
    await audit_service.log_action(
        db, user, "kb:create", "kb", kb.id,
        {"name": kb.name, "is_public": kb.is_public},
        client_ip(request),
    )
    resp = KnowledgeBaseResponse.model_validate(kb)
    resp.document_count = 0
    resp.my_role = KBMemberRole.OWNER.value
    return success_response(resp, message="知识库创建成功")


@router.get("")
async def list_knowledge_bases(
    db: DB,
    user: CurrentUser,
):
    """获取知识库列表：仅返回本人拥有/加入/公开的知识库（Phase 7 隔离）。"""
    member_roles = await _load_member_roles(db, user.id)
    stmt = (
        select(KnowledgeBase)
        .options(selectinload(KnowledgeBase.documents))
        .where(
            or_(
                KnowledgeBase.owner_id == user.id,
                KnowledgeBase.is_public.is_(True),
                KnowledgeBase.id.in_(member_roles.keys()),
            )
        )
        .order_by(KnowledgeBase.id)
    )
    result = await db.execute(stmt)
    kbs = result.scalars().all()
    resp_list = []
    for kb in kbs:
        role = "owner" if kb.owner_id == user.id else member_roles.get(kb.id, "viewer")
        resp_list.append(_to_response(kb, role))
    return success_response(resp_list)


@router.get("/{kb_id}")
async def get_knowledge_base(
    kb_id: int,
    db: DB,
    user: CurrentUser,
    _: Annotated[User, Depends(require_kb_role("viewer"))],
):
    """获取知识库详情（viewer 及以上可访问）。"""
    kb = await _get_kb(db, kb_id)
    role = "owner" if kb.owner_id == user.id else KBMemberRole.VIEWER.value
    return success_response(_to_response(kb, role))


@router.patch("/{kb_id}")
async def update_knowledge_base(
    kb_id: int,
    body: KnowledgeBaseUpdate,
    db: DB,
    user: CurrentUser,
    request: Request,
    _: Annotated[User, Depends(require_kb_role("owner"))],
):
    """更新知识库信息/配置（仅 owner）。"""
    kb = await _get_kb(db, kb_id)
    changed = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    for field, value in changed.items():
        setattr(kb, field, value)
    await audit_service.log_action(
        db, user, "kb:update", "kb", kb_id, {"changed": changed}, client_ip(request),
    )
    return success_response(_to_response(kb, "owner"), message="更新成功")


@router.delete("/{kb_id}")
async def delete_knowledge_base(
    kb_id: int,
    db: DB,
    user: CurrentUser,
    request: Request,
    _: Annotated[User, Depends(require_kb_role("owner"))],
):
    """删除知识库（仅 owner）：Chroma collection + 文件 + 数据库级联。"""
    kb = await _get_kb(db, kb_id)
    from app.db import chroma_store

    # 1. 删除 Chroma 向量集合
    chroma_store.delete_collection(kb_id)
    # 2. 删除磁盘文件
    for doc in kb.documents:
        if doc.storage_path:
            delete_file(doc.storage_path)
    # 3. 数据库级联删除（documents / kb_members）
    await audit_service.log_action(
        db, user, "kb:delete", "kb", kb_id, {"name": kb.name}, client_ip(request),
    )
    await db.delete(kb)
    return success_response(None, message="知识库已删除")


# ========== 成员管理（仅 owner） ==========


@router.get("/{kb_id}/members")
async def list_members(
    kb_id: int,
    db: DB,
    _: Annotated[User, Depends(require_kb_role("owner"))],
):
    """列出知识库成员（仅 owner）。"""
    result = await db.execute(
        select(KnowledgeBaseMember, User.username)
        .join(User, KnowledgeBaseMember.user_id == User.id)
        .where(KnowledgeBaseMember.kb_id == kb_id)
        .order_by(KnowledgeBaseMember.id)
    )
    members = [
        KBMemberResponse(user_id=m.user_id, username=username, role=m.role.value)
        for m, username in result.all()
    ]
    return success_response(members)


@router.post("/{kb_id}/members")
async def add_member(
    kb_id: int,
    body: KBMemberCreate,
    db: DB,
    user: CurrentUser,
    request: Request,
    _: Annotated[User, Depends(require_kb_role("owner"))],
):
    """添加成员（仅 owner）。"""
    kb = await _get_kb(db, kb_id)
    if body.user_id == kb.owner_id:
        raise BadRequestError("owner 无需添加为成员")

    target = await db.get(User, body.user_id)
    if target is None:
        raise NotFoundError(f"用户 {body.user_id} 不存在")

    stmt = select(KnowledgeBaseMember).where(
        KnowledgeBaseMember.kb_id == kb_id, KnowledgeBaseMember.user_id == body.user_id
    )
    if (await db.execute(stmt)).scalar_one_or_none():
        raise ConflictError(f"用户 {body.user_id} 已是成员")

    member = KnowledgeBaseMember(kb_id=kb_id, user_id=body.user_id, role=body.role)
    db.add(member)
    await db.flush()
    await audit_service.log_action(
        db, user, "kb:member_add", "kb", kb_id,
        {"user_id": body.user_id, "username": target.username, "role": body.role.value},
        client_ip(request),
    )
    return success_response(
        KBMemberResponse(user_id=target.id, username=target.username, role=body.role.value),
        message="成员添加成功",
    )


@router.patch("/{kb_id}/members/{user_id}")
async def update_member(
    kb_id: int,
    user_id: int,
    body: KBMemberUpdate,
    db: DB,
    user: CurrentUser,
    request: Request,
    _: Annotated[User, Depends(require_kb_role("owner"))],
):
    """修改成员角色（仅 owner，owner 本人角色不可改）。"""
    kb = await _get_kb(db, kb_id)
    if user_id == kb.owner_id:
        raise BadRequestError("owner 角色不可修改")

    stmt = select(KnowledgeBaseMember).where(
        KnowledgeBaseMember.kb_id == kb_id, KnowledgeBaseMember.user_id == user_id
    )
    member = (await db.execute(stmt)).scalar_one_or_none()
    if member is None:
        raise NotFoundError(f"用户 {user_id} 不是知识库 {kb_id} 的成员")

    old_role = member.role
    member.role = body.role
    await audit_service.log_action(
        db, user, "kb:member_update", "kb", kb_id,
        {"user_id": user_id, "old_role": old_role.value, "new_role": body.role.value},
        client_ip(request),
    )
    return success_response(
        KBMemberResponse(user_id=user_id, username="", role=body.role.value), message="角色已更新"
    )


@router.delete("/{kb_id}/members/{user_id}")
async def remove_member(
    kb_id: int,
    user_id: int,
    db: DB,
    user: CurrentUser,
    request: Request,
    _: Annotated[User, Depends(require_kb_role("owner"))],
):
    """移除成员（仅 owner，owner 本人不可移除）。"""
    kb = await _get_kb(db, kb_id)
    if user_id == kb.owner_id:
        raise BadRequestError("owner 不可被移除")

    stmt = select(KnowledgeBaseMember).where(
        KnowledgeBaseMember.kb_id == kb_id, KnowledgeBaseMember.user_id == user_id
    )
    member = (await db.execute(stmt)).scalar_one_or_none()
    if member is None:
        raise NotFoundError(f"用户 {user_id} 不是知识库 {kb_id} 的成员")

    await audit_service.log_action(
        db, user, "kb:member_remove", "kb", kb_id, {"user_id": user_id}, client_ip(request),
    )
    await db.delete(member)
    return success_response(None, message="成员已移除")


