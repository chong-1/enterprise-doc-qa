"""对话历史管理 API。"""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_conversations():
    """获取对话列表。"""
    pass


@router.get("/{conversation_id}/messages")
async def get_messages():
    """获取对话中的消息列表。"""
    pass


@router.delete("/{conversation_id}")
async def delete_conversation():
    """删除对话。"""
    pass
