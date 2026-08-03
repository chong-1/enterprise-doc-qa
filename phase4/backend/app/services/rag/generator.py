"""LLM 生成服务：拼装 System Prompt + 上下文 → 调 LLM 输出答案。

支持非流式和 SSE 流式两种模式，引用格式化。
"""

from collections.abc import AsyncIterator

from app.core.config import settings
from app.services.llm import get_llm_backend
from app.services.llm.base import ChatMessage
from app.services.document.chunker import get_tokenizer

SYSTEM_PROMPT = """你是一个专业的企业文档问答助手。请根据提供的文档资料回答用户问题。

要求：
1. 只根据提供的文档内容回答，不要编造信息
2. 如果文档中没有相关信息，请明确说"根据现有文档，无法找到相关信息"
3. 回答应简洁、准确，引用具体数据
4. 如果涉及多个文档来源，请分别说明
5. 用中文回答"""


def _format_context(candidates: list[dict]) -> str:
    """将检索结果格式化为 LLM 上下文。"""
    parts: list[str] = []
    for i, c in enumerate(candidates, 1):
        meta = c.get("metadata", {})
        source = f"{meta.get('filename', '未知文档')}"
        parts.append(f"[资料{i}] 来源：{source}\n{c['text']}")
    return "\n\n".join(parts)


def _estimate_tokens(text: str) -> int:
    """用 BGE-M3 tokenizer 估算 token 数。"""
    tok = get_tokenizer()
    return len(tok.encode(text, add_special_tokens=False))


def _trim_context(candidates: list[dict], max_tokens: int = 3000) -> list[dict]:
    """按 token 预算裁剪上下文，保留最相关的。"""
    trimmed: list[dict] = []
    total = 0
    for c in candidates:
        n = _estimate_tokens(c["text"])
        if total + n > max_tokens:
            break
        trimmed.append(c)
        total += n
    return trimmed


async def generate_answer(
    question: str,
    candidates: list[dict],
    conversation_history: list[ChatMessage] | None = None,
) -> str:
    """非流式生成答案。"""
    trimmed = _trim_context(candidates)
    context = _format_context(trimmed)

    messages = [ChatMessage(role="system", content=SYSTEM_PROMPT)]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append(
        ChatMessage(
            role="user",
            content=f"请根据以下资料回答问题：\n\n{context}\n\n问题：{question}",
        )
    )
    llm = get_llm_backend()
    return await llm.chat(messages)


async def generate_answer_stream(
    question: str,
    candidates: list[dict],
    conversation_history: list[ChatMessage] | None = None,
) -> AsyncIterator[str]:
    """流式生成答案（SSE），逐 token yield。"""
    trimmed = _trim_context(candidates)
    context = _format_context(trimmed)

    messages = [ChatMessage(role="system", content=SYSTEM_PROMPT)]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append(
        ChatMessage(
            role="user",
            content=f"请根据以下资料回答问题：\n\n{context}\n\n问题：{question}",
        )
    )
    llm = get_llm_backend()
    async for token in llm.chat_stream(messages):
        yield token


def format_citations(candidates: list[dict]) -> list[dict]:
    """从检索结果中提取引用信息。"""
    citations: list[dict] = []
    for c in candidates:
        meta = c.get("metadata", {})
        citations.append({
            "document": meta.get("filename", "未知"),
            "chunk_index": meta.get("chunk_idx", 0),
            "text": c["text"][:200] + ("..." if len(c["text"]) > 200 else ""),
            "score": c.get("rerank_score", c.get("score", 0)),
        })
    return citations
