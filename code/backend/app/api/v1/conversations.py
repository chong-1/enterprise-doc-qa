"""对话管理 API：列表 / 详情 / 删除 / 消息列表。"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.core.dependencies import DB, CurrentUser
from app.core.exceptions import NotFoundError, paginated_response, success_response
from app.schemas.qa import ConversationResponse, MessageResponse, SourceCitation
from app.services import conversation_service

router = APIRouter()


@router.get("")
async def list_conversations(
    db: DB,
    user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """当前用户的对话列表（按更新时间倒序）。"""
    convs, total = await conversation_service.list_conversations(db, user, page, page_size)
    items = [
        ConversationResponse(
            id=c.id,
            title=c.title,
            kb_id=c.kb_id,
            message_count=len(c.messages),
            created_at=c.created_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(c.created_at, "strftime") else str(c.created_at),
            updated_at=c.updated_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(c.updated_at, "strftime") else str(c.updated_at),
        )
        for c in convs
    ]
    return paginated_response(items=items, total=total, page=page, page_size=page_size)


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: int, db: DB, user: CurrentUser):
    """对话详情。"""
    conv = await conversation_service.get_conversation(db, conversation_id, user)
    return success_response(
        ConversationResponse(
            id=conv.id,
            title=conv.title,
            kb_id=conv.kb_id,
            message_count=len(conv.messages),
            created_at=conv.created_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(conv.created_at, "strftime") else str(conv.created_at),
            updated_at=conv.updated_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(conv.updated_at, "strftime") else str(conv.updated_at),
        )
    )


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: int, db: DB, user: CurrentUser):
    """删除对话（级联删除消息和引用）。"""
    await conversation_service.delete_conversation(db, conversation_id, user)
    await conversation_service.clear_context(conversation_id)
    await db.flush()
    return success_response(None, message="删除成功")


@router.get("/{conversation_id}/messages")
async def get_messages(
    conversation_id: int,
    db: DB,
    user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    """对话的消息列表（分页，含引用）。"""
    msgs, total = await conversation_service.list_messages(db, conversation_id, user, page, page_size)
    items = [
        MessageResponse(
            id=m.id,
            role=m.role.value,
            content=m.content,
            tokens_used=m.tokens_used,
            citations=[
                SourceCitation(
                    document=str(c.document_id or ""),
                    chunk_index=c.chunk_index,
                    text=c.cited_text or "",
                    score=c.score,
                )
                for c in (m.citations or [])
            ],
            created_at=m.created_at if isinstance(m.created_at, str) else str(m.created_at),
        )
        for m in msgs
    ]
    return paginated_response(items=items, total=total, page=page, page_size=page_size)
