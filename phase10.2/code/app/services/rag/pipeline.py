"""RAG 完整流水线编排：检索 → 重排 → 生成。

这是整个 RAG 系统的入口，对外暴露两个接口：
- query(): 非流式问答
- query_stream(): SSE 流式问答

注入防御（附加式，不改变原有流程，见 services/injection_guard.py）：
- 检索结果过滤：剔除含注入特征的 chunk
- 问答审计：记录检索片段 + 剔除结果 + 输出校验结果（qa:retrieval）
- 输出侧校验：扫描答案是否泄露密钥/系统提示词
"""

import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.core.config import settings
from app.db.session import async_session_factory
from app.services import system_config_service
from app.services.injection_guard import filter_injection, scan_answer
from app.services.llm.base import ChatMessage
from app.services.rag import retriever
from app.services.rag.generator import format_citations, generate_answer, generate_answer_stream
from app.services.rag.query_cache import get_cached_answer, set_cached_answer

logger = logging.getLogger(__name__)


@dataclass
class RAGResult:
    answer: str
    citations: list[dict]
    processing_time_ms: int
    from_cache: bool = False


class RAGPipeline:
    """RAG 流水线：检索 + 重排 + 生成。"""

    def __init__(self) -> None:
        pass

    async def _top_k(self) -> int:
        """从系统配置读取 rag.top_k（默认 5，跳过 Reranker 节省内存）。"""
        async with async_session_factory() as db:
            return await system_config_service.get_int_config(db, "rag.top_k", 5)

    async def _rank_candidates(self, kb_id: int, question: str) -> list[dict]:
        """混合检索 + 截取 top_k。"""
        candidates = retriever.hybrid_search(kb_id, question)
        top_k = await self._top_k()
        return sorted(candidates, key=lambda c: c.get("score", 0), reverse=True)[:top_k]

    async def _audit_retrieval(
        self,
        kb_id: int,
        question: str,
        candidates: list[dict],
        dropped: list[str],
        answer_hits: list[str] | None = None,
    ) -> None:
        """审计每次问答的检索上下文（附加式：失败不影响问答主流程）。

        记录检索片段 + 注入剔除结果 + 输出校验结果，事后可回溯攻击。
        """
        from app.services.audit_service import log_action

        try:
            async with async_session_factory() as db:
                await log_action(
                    db,
                    None,
                    "qa:retrieval",
                    "qa",
                    kb_id,
                    {
                        "question": question[:200],
                        "snippets": [c["text"][:300] for c in candidates[:3]],
                        "dropped": dropped[:10],
                        "answer_hits": answer_hits or [],
                    },
                )
                await db.commit()
        except Exception:
            logger.exception("问答审计失败（不影响问答）: kb_id=%s", kb_id)

    async def query(
        self,
        question: str,
        kb_id: int,
        conversation_history: list[ChatMessage] | None = None,
    ) -> RAGResult:
        """非流式问答：搜索 → 生成 → 返回完整结果。

        高并发优化：命中答案缓存直接返回（跳过 embedding 推理和 LLM 调用）。
        """
        t0 = time.monotonic()

        # 0. 答案缓存（热门重复问题直接短路，0 次推理 + 0 次 API）
        cached = await get_cached_answer(kb_id, question)
        if cached:
            return RAGResult(
                answer=cached["answer"],
                citations=cached["citations"],
                processing_time_ms=0,
                from_cache=True,
            )

        # 1. 混合检索 + 截取 top_k + 注入过滤
        candidates = await self._rank_candidates(kb_id, question)
        candidates, dropped = filter_injection(candidates)

        # 2. LLM 生成答案
        answer = await generate_answer(question, candidates, conversation_history)

        # 3. 输出侧校验（密钥/系统提示词泄露扫描，附加式不阻断）
        answer_hits = scan_answer(answer)
        if answer_hits:
            logger.warning("答案输出疑似泄露: kb_id=%s 命中=%s", kb_id, ",".join(answer_hits))

        # 4. 审计 + 引用溯源 + 写缓存
        await self._audit_retrieval(kb_id, question, candidates, dropped, answer_hits)
        citations = format_citations(candidates)
        await set_cached_answer(kb_id, question, answer.strip(), citations)

        elapsed = int((time.monotonic() - t0) * 1000)
        return RAGResult(answer=answer.strip(), citations=citations, processing_time_ms=elapsed)

    async def query_stream(
        self,
        question: str,
        kb_id: int,
        conversation_history: list[ChatMessage] | None = None,
    ) -> AsyncIterator[str]:
        """流式问答：搜索 → 重排 → 流式生成（SSE）。

        缓存命中时模拟流式输出（按片段切分），保持前端 SSE 兼容。
        """
        # 0. 答案缓存：命中则模拟流式逐段输出
        cached = await get_cached_answer(kb_id, question)
        if cached:
            full = cached["answer"]
            step = 4  # 每次推 4 字符，保持打字机效果
            for i in range(0, len(full), step):
                yield full[i : i + step]
            return

        # 1. 混合检索 + 截取 top_k + 注入过滤
        candidates = await self._rank_candidates(kb_id, question)
        candidates, dropped = filter_injection(candidates)
        await self._audit_retrieval(kb_id, question, candidates, dropped)

        # 2. 流式输出（同时收集完整答案用于写缓存 + 输出侧校验）
        parts: list[str] = []
        async for token in generate_answer_stream(question, candidates, conversation_history):
            parts.append(token)
            yield token
        answer = "".join(parts)
        answer_hits = scan_answer(answer)
        if answer_hits:
            logger.warning("答案输出疑似泄露: kb_id=%s 命中=%s", kb_id, ",".join(answer_hits))
        await set_cached_answer(kb_id, question, answer.strip(), format_citations(candidates))
