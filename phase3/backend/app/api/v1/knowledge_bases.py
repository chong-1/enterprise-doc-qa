"""知识库 CRUD API（Phase 3 最小实现：创建 / 列表 / 详情）。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.dependencies import DB, CurrentUser, require_permission
from app.core.exceptions import NotFoundError, success_response
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseResponse

router = APIRouter()


def _to_response(kb: KnowledgeBase) -> KnowledgeBaseResponse:
    """ORM → 响应（补 document_count）。"""
    resp = KnowledgeBaseResponse.model_validate(kb)
    resp.document_count = len(kb.documents)
    return resp


@router.post("")
async def create_knowledge_base(
    body: KnowledgeBaseCreate,
    db: DB,
    user: CurrentUser,
    _: Annotated[User, Depends(require_permission("kb:create"))],
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
    # 注意：不能给 kb.documents 赋值来补 document_count——relationship 赋值会先读取旧值
    # 触发 lazy load（async 下 MissingGreenlet）。新建知识库文档数必为 0，直接构造。
    resp = KnowledgeBaseResponse.model_validate(kb)
    resp.document_count = 0
    return success_response(resp, message="知识库创建成功")


@router.get("")
async def list_knowledge_bases(
    db: DB,
    _: CurrentUser,
):
    """获取知识库列表（Phase 7 再实现权限隔离，当前返回全部）。"""
    stmt = select(KnowledgeBase).options(selectinload(KnowledgeBase.documents)).order_by(KnowledgeBase.id)
    result = await db.execute(stmt)
    kbs = result.scalars().all()
    return success_response([_to_response(kb) for kb in kbs])


@router.get("/{kb_id}")
async def get_knowledge_base(
    kb_id: int,
    db: DB,
    _: CurrentUser,
):
    """获取知识库详情。"""
    stmt = (
        select(KnowledgeBase)
        .options(selectinload(KnowledgeBase.documents))
        .where(KnowledgeBase.id == kb_id)
    )
    result = await db.execute(stmt)
    kb = result.scalar_one_or_none()
    if kb is None:
        raise NotFoundError(f"知识库 {kb_id} 不存在")
    return success_response(_to_response(kb))
