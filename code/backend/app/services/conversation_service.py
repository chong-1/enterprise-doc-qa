"""对话管理服务：CRUD / 消息存储 / 标题生成 / 摘要压缩。"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.db.redis_client import get_redis
from app.models.conversation import Conversation, Message, MessageCitation, MessageRole
from app.models.user import User


# ========== 对话 CRUD ==========


async def create_conversation(
    db: AsyncSession, user: User, kb_id: int | None, title: str = "新对话"
) -> Conversation:
    conv = Conversation(user_id=user.id, kb_id=kb_id, title=title)
    db.add(conv)
    await db.flush()
    return conv


async def list_conversations(
    db: AsyncSession, user: User, page: int = 1, page_size: int = 20
) -> tuple[list[Conversation], int]:
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .options(selectinload(Conversation.messages))
    )
    count_stmt = (
        select(func.count()).select_from(Conversation).where(Conversation.user_id == user.id)
    )
    total = (await db.execute(count_stmt)).scalar() or 0
    result = await db.execute(
        stmt.order_by(Conversation.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return list(result.scalars().all()), total


async def get_conversation(db: AsyncSession, conv_id: int, user: User) -> Conversation:
    conv = await db.get(Conversation, conv_id, options=[selectinload(Conversation.messages)])
    if conv is None or conv.user_id != user.id:
        raise NotFoundError(f"对话 {conv_id} 不存在")
    return conv


async def delete_conversation(db: AsyncSession, conv_id: int, user: User) -> None:
    conv = await get_conversation(db, conv_id, user)
    await db.delete(conv)


# ========== 消息 ==========


async def save_message(
    db: AsyncSession,
    conversation_id: int,
    role: str,
    content: str,
    tokens_used: int = 0,
    processing_time_ms: int = 0,
) -> Message:
    msg = Message(
        conversation_id=conversation_id,
        role=MessageRole(role),
        content=content,
        tokens_used=tokens_used,
        processing_time_ms=processing_time_ms,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    db.add(msg)
    # touch 对话的 updated_at
    conv = await db.get(Conversation, conversation_id)
    if conv:
        conv.updated_at = datetime.now()
    await db.flush()
    return msg


async def save_citation(
    db: AsyncSession,
    message_id: int,
    document_id: int | None,
    chunk_index: int,
    score: float,
    cited_text: str,
) -> MessageCitation:
    cit = MessageCitation(
        message_id=message_id,
        document_id=document_id,
        chunk_index=chunk_index,
        score=score,
        cited_text=cited_text,
    )
    db.add(cit)
    await db.flush()
    return cit


async def list_messages(
    db: AsyncSession, conv_id: int, user: User, page: int = 1, page_size: int = 50
) -> tuple[list[Message], int]:
    conv = await get_conversation(db, conv_id, user)
    stmt = select(Message).where(Message.conversation_id == conv_id).options(
        selectinload(Message.citations)
    )
    count_stmt = select(func.count()).select_from(Message).where(Message.conversation_id == conv_id)
    total = (await db.execute(count_stmt)).scalar() or 0
    result = await db.execute(
        stmt.order_by(Message.id).offset((page - 1) * page_size).limit(page_size)
    )
    return list(result.scalars().all()), total


# ========== 标题自动生成 ==========

TITLE_PROMPT = """根据用户的第一条消息，生成一个简短的对话标题（不超过 20 个字）。
直接返回标题文本，不要加引号、标点或额外解释。"""


async def generate_title(question: str) -> str:
    import asyncio
    from app.services.llm import get_llm_backend
    from app.services.llm.base import ChatMessage

    llm = get_llm_backend()
    try:
        title = await asyncio.wait_for(
            llm.chat(
                [ChatMessage(role="system", content=TITLE_PROMPT),
                 ChatMessage(role="user", content=question)],
                max_tokens=50, temperature=0.3,
            ),
            timeout=10,
        )
        result = title.strip().strip("'\"").strip()[:50]
        if result:
            return result
    except Exception:
        pass
    # Fallback: 截断问题作为标题
    q = question.strip()[:30]
    return q + ("..." if len(question) > 30 else "")


# ========== Redis 短期记忆 ==========

MEMORY_KEY_PREFIX = "conv_memory:"
MAX_RECENT_ROUNDS = 10  # 最近 10 对消息


async def get_context(conversation_id: int) -> list[dict]:
    """从 Redis 获取最近消息上下文。

    注意：add_to_context 用 rpush 追加（最老的在队头），lrange 返回的即
    时间正序 [最老, ..., 最新]，不能 reverse——否则 Agent 拿到的对话历史
    是倒叙，上下文记忆会错乱。
    """
    r = await get_redis()
    key = f"{MEMORY_KEY_PREFIX}{conversation_id}"
    raw = await r.lrange(key, 0, -1)
    import json
    return [json.loads(m) for m in raw]


async def add_to_context(conversation_id: int, role: str, content: str) -> None:
    """追加一条消息到 Redis 上下文队列。"""
    r = await get_redis()
    key = f"{MEMORY_KEY_PREFIX}{conversation_id}"
    import json
    await r.rpush(key, json.dumps({"role": role, "content": content}, ensure_ascii=False))
    # 只保留最近 MAX_RECENT_ROUNDS * 2 条
    await r.ltrim(key, -MAX_RECENT_ROUNDS * 2, -1)


async def clear_context(conversation_id: int) -> None:
    r = await get_redis()
    await r.delete(f"{MEMORY_KEY_PREFIX}{conversation_id}")


# ========== 长期记忆摘要压缩 ==========

SUMMARY_PROMPT = """将以下对话历史总结为一段简洁的摘要（不超过 200 字）。
保留关键事实、数字、决策和结论。用中文。"""


async def summarize_and_compress(db: AsyncSession, conversation_id: int) -> str | None:
    """当上下文超过 MAX_RECENT_ROUNDS 时，压缩老消息为摘要存入对话记录。"""
    r = await get_redis()
    key = f"{MEMORY_KEY_PREFIX}{conversation_id}"
    total = await r.llen(key)

    if total <= MAX_RECENT_ROUNDS * 2:
        return None  # 不需要压缩

    # 取出最老的超出部分
    overflow_count = total - MAX_RECENT_ROUNDS * 2
    old_messages = await r.lrange(key, 0, overflow_count - 1)
    # 从队列头部删除
    await r.ltrim(key, overflow_count, -1)

    import json
    texts = [json.loads(m)["content"] for m in old_messages]
    old_text = "\n".join(texts[:20])  # 最多取 20 条压缩

    from app.services.llm import get_llm_backend
    from app.services.llm.base import ChatMessage

    llm = get_llm_backend()
    try:
        summary = await llm.chat(
            [ChatMessage(role="system", content=SUMMARY_PROMPT),
             ChatMessage(role="user", content=old_text)],
            max_tokens=300, temperature=0.3,
        )
        # 摘要作为 system 消息插入 Redis 队列头部
        await r.lpush(key, json.dumps({"role": "system", "content": f"[历史摘要] {summary.strip()}"}, ensure_ascii=False))
        return summary.strip()
    except Exception:
        return None
