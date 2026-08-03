"""RAG 问答 API（非流式 + SSE 流式）。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.core.dependencies import DB, CurrentUser
from app.core.exceptions import BadRequestError, NotFoundError, success_response
from app.models.knowledge_base import KnowledgeBase
from app.schemas.qa import QANonStreamResponse, QARequest, SourceCitation
from app.services.rag.pipeline import RAGPipeline

router = APIRouter()

# 全局流水线实例（无状态，可共用）
_pipeline = RAGPipeline()


@router.post("/{kb_id}")
async def ask_question(
    kb_id: int,
    body: QARequest,
    db: DB = None,
    _: CurrentUser = None,
):
    """向知识库提问（支持流式 SSE 和非流式两种模式）。"""
    # 校验知识库存在
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise NotFoundError(f"知识库 {kb_id} 不存在")

    if body.stream:
        return EventSourceResponse(
            _stream_answer(kb_id, body.question),
            media_type="text/event-stream",
        )
    else:
        result = await _pipeline.query(body.question, kb_id)
        return success_response(
            QANonStreamResponse(
                answer=result.answer,
                citations=[
                    SourceCitation(
                        document=c.get("document", ""),
                        chunk_index=c.get("chunk_index", 0),
                        text=c["text"],
                        score=c.get("score", 0),
                    )
                    for c in result.citations
                ],
                processing_time_ms=result.processing_time_ms,
            )
        )


async def _stream_answer(kb_id: int, question: str):
    """SSE 流式生成器。"""
    answer_parts: list[str] = []
    async for token in _pipeline.query_stream(question, kb_id):
        answer_parts.append(token)
        yield {"event": "token", "data": token}
    full = "".join(answer_parts)
    yield {"event": "done", "data": full}
