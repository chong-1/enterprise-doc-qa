"""RAG 完整流水线编排：检索 → 重排 → 生成。

这是整个 RAG 系统的入口，对外暴露两个接口：
- query(): 非流式问答
- query_stream(): SSE 流式问答
"""

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.services.llm.base import ChatMessage
from app.services.rag import retriever
from app.services.rag.generator import format_citations, generate_answer, generate_answer_stream


@dataclass
class RAGResult:
    answer: str
    citations: list[dict]
    processing_time_ms: int


class RAGPipeline:
    """RAG 流水线：检索 + 重排 + 生成。"""

    def __init__(self) -> None:
        pass

    async def query(
        self,
        question: str,
        kb_id: int,
        conversation_history: list[ChatMessage] | None = None,
    ) -> RAGResult:
        """非流式问答：搜索 → 生成 → 返回完整结果。"""
        t0 = time.monotonic()

        # 1. 混合检索
        candidates = retriever.hybrid_search(kb_id, question)

        # 2. 取 top_k=5（跳过 Reranker 节省内存，混合检索的 RRF 分数已足够好）
        candidates = sorted(candidates, key=lambda c: c.get("score", 0), reverse=True)[:5]

        # 3. LLM 生成答案
        answer = await generate_answer(question, candidates, conversation_history)

        # 4. 引用溯源
        citations = format_citations(candidates)

        elapsed = int((time.monotonic() - t0) * 1000)
        return RAGResult(answer=answer.strip(), citations=citations, processing_time_ms=elapsed)

    async def query_stream(
        self,
        question: str,
        kb_id: int,
        conversation_history: list[ChatMessage] | None = None,
    ) -> AsyncIterator[str]:
        """流式问答：搜索 → 重排 → 流式生成（SSE）。"""
        # 1 + 2 同非流式
        candidates = retriever.hybrid_search(kb_id, question)
        candidates = sorted(candidates, key=lambda c: c.get("score", 0), reverse=True)[:5]

        # 3. 流式输出
        async for token in generate_answer_stream(question, candidates, conversation_history):
            yield token
