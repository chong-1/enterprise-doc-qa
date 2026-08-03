"""RAG 问答 API（非流式 + SSE 流式 + Agent 模式）。"""

import time
from typing import Annotated

from fastapi import APIRouter, Depends
from langchain_core.messages import HumanMessage, AIMessage
from sse_starlette.sse import EventSourceResponse

from app.core.dependencies import DB, CurrentUser
from app.core.exceptions import NotFoundError, success_response
from app.models.knowledge_base import KnowledgeBase
from app.schemas.qa import QANonStreamResponse, QARequest, SourceCitation
from app.services.agent.memory import add_message, get_history
from app.services.rag.pipeline import RAGPipeline

router = APIRouter()

_pipeline = RAGPipeline()


@router.post("/{kb_id}")
async def ask_question(
    kb_id: int,
    body: QARequest,
    db: DB = None,
    _: CurrentUser = None,
):
    """向知识库提问。agent_mode=True 启用 Router + ReAct 智能编排。"""
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise NotFoundError(f"知识库 {kb_id} 不存在")

    if body.agent_mode:
        return await _agent_answer(kb_id, body.question, body.conversation_id)

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
                    ) for c in result.citations
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
    yield {"event": "done", "data": "".join(answer_parts)}


# ========== Agent Mode ==========

async def _agent_answer(kb_id: int, question: str, conversation_id: int | None) -> dict:
    """Agent 模式：Router → RAG/ReAct → 答案 + 思考链。"""
    t0 = time.monotonic()
    from app.services.agent.graph import get_agent_graph

    history = get_history(conversation_id)
    messages = history + [HumanMessage(content=question)]

    graph = get_agent_graph()
    result = await graph.ainvoke({
        "messages": messages,
        "kb_id": kb_id,
        "thought_chain": [],
        "final_answer": "",
        "citations": [],
    })

    # 记忆存储
    if conversation_id:
        add_message(conversation_id, HumanMessage(content=question))
        add_message(conversation_id, AIMessage(content=result.get("final_answer", "")))

    elapsed = int((time.monotonic() - t0) * 1000)
    return success_response(
        QANonStreamResponse(
            answer=result.get("final_answer", ""),
            citations=[
                SourceCitation(
                    document=c.get("document", ""),
                    chunk_index=c.get("chunk_index", 0),
                    text=c.get("text", ""),
                    score=c.get("score", 0),
                ) for c in result.get("citations", [])
            ],
            thought_chain=result.get("thought_chain", []),
            processing_time_ms=elapsed,
        )
    )
