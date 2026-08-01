"""RAG 问答 API（含 SSE 流式）。"""

from fastapi import APIRouter

router = APIRouter()


@router.post("")
async def ask_question():
    """向知识库提问（支持流式 SSE）。"""
    pass
