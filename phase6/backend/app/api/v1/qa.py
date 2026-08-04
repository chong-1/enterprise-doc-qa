"""RAG 问答 API（非流式 + SSE 流式 + Agent 模式 + 对话记忆）。"""

import time
from typing import Annotated

from fastapi import APIRouter
from langchain_core.messages import HumanMessage, AIMessage
from sse_starlette.sse import EventSourceResponse

from app.core.dependencies import DB, CurrentUser
from app.core.exceptions import NotFoundError, success_response
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.schemas.qa import QANonStreamResponse, QARequest, SourceCitation
from app.services import conversation_service
from app.services.rag.pipeline import RAGPipeline

router = APIRouter()
_pipeline = RAGPipeline()


@router.post("/{kb_id}")
async def ask_question(
    kb_id: int,
    body: QARequest,
    db: DB = None,
    user: CurrentUser = None,
):
    """向知识库提问。支持对话记忆、Agent 模式、SSE 流式。"""
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise NotFoundError(f"知识库 {kb_id} 不存在")

    # 对话管理：无 conversation_id 时自动创建
    conv_id = body.conversation_id
    if conv_id is None:
        conv = await conversation_service.create_conversation(db, user, kb_id)
        conv_id = conv.id
        # 首条消息 → 异步生成标题
        try:
            title = await conversation_service.generate_title(body.question)
        except Exception:
            title = body.question[:30]
        conv.title = title
        await db.flush()

    # Agent 模式
    if body.agent_mode:
        return await _agent_answer(kb_id, body.question, conv_id, db)

    # 流式
    if body.stream:
        return EventSourceResponse(
            _stream_answer(kb_id, body.question, conv_id, db),
            media_type="text/event-stream",
        )

    # 非流式
    t0 = time.monotonic()
    result = await _pipeline.query(body.question, kb_id)
    elapsed = int((time.monotonic() - t0) * 1000)

    # 存储消息 + 记忆
    await _save_qa_result(db, conv_id, body.question, result.answer, elapsed, result.citations)

    return success_response(
        QANonStreamResponse(
            answer=result.answer,
            conversation_id=conv_id,
            citations=[_to_citation(c) for c in result.citations],
            processing_time_ms=elapsed,
        )
    )


async def _stream_answer(kb_id: int, question: str, conv_id: int, db):
    """SSE 流式生成器。"""
    answer_parts: list[str] = []
    async for token in _pipeline.query_stream(question, kb_id):
        answer_parts.append(token)
        yield {"event": "token", "data": token}
    full = "".join(answer_parts)
    await _save_qa_result(db, conv_id, question, full, 0, [])
    yield {"event": "done", "data": full}


# ========== Agent Mode ==========

async def _agent_answer(kb_id: int, question: str, conv_id: int, db) -> dict:
    t0 = time.monotonic()
    from app.services.agent.graph import get_agent_graph

    # 从 Redis 加载上下文
    ctx = await conversation_service.get_context(conv_id)
    history_msgs = []
    for m in ctx:
        if m["role"] == "user":
            history_msgs.append(HumanMessage(content=m["content"]))
        elif m["role"] == "assistant":
            history_msgs.append(AIMessage(content=m["content"]))

    graph = get_agent_graph()
    result = await graph.ainvoke({
        "messages": history_msgs + [HumanMessage(content=question)],
        "kb_id": kb_id,
        "thought_chain": [],
        "final_answer": "",
        "citations": [],
    })

    answer = result.get("final_answer", "")
    citations = result.get("citations", [])
    elapsed = int((time.monotonic() - t0) * 1000)

    # 存储消息 + 记忆 + 摘要压缩
    await _save_qa_result(db, conv_id, question, answer, elapsed, citations)
    await conversation_service.summarize_and_compress(db, conv_id)

    return success_response(
        QANonStreamResponse(
            answer=answer,
            conversation_id=conv_id,
            citations=[_to_citation(c) for c in citations],
            thought_chain=result.get("thought_chain", []),
            processing_time_ms=elapsed,
        )
    )


# ========== Helpers ==========

async def _save_qa_result(
    db, conv_id: int, question: str, answer: str, elapsed: int, citations: list[dict]
) -> None:
    """保存问答到 MySQL + Redis。"""
    # MySQL 消息
    await conversation_service.save_message(db, conv_id, "user", question)
    msg = await conversation_service.save_message(
        db, conv_id, "assistant", answer, processing_time_ms=elapsed,
    )
    for c in citations:
        doc_name = c.get("document", "")
        doc_id = None
        try:
            doc_id = int(doc_name) if doc_name.isdigit() else None
        except Exception:
            pass
        await conversation_service.save_citation(
            db, msg.id, doc_id, c.get("chunk_index", 0), c.get("score", 0), c.get("text", ""),
        )
    await db.commit()

    # Redis 短期记忆
    await conversation_service.add_to_context(conv_id, "user", question)
    await conversation_service.add_to_context(conv_id, "assistant", answer)


def _to_citation(c: dict) -> SourceCitation:
    return SourceCitation(
        document=c.get("document", ""),
        chunk_index=c.get("chunk_index", 0),
        text=c.get("text", ""),
        score=c.get("score", 0),
    )
