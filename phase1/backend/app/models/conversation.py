"""对话 & 消息 & 引用模型。"""

from typing import Optional

from sqlalchemy import BigInteger, Enum, Float, ForeignKey, Integer, String, Text, LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, IntPKMixin

import enum


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Conversation(Base, IntPKMixin, TimestampMixin):
    __tablename__ = "conversations"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="用户"
    )
    kb_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("knowledge_bases.id", ondelete="SET NULL"), nullable=True, comment="关联知识库"
    )
    title: Mapped[str] = mapped_column(String(500), default="新对话", comment="对话标题")

    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.id"
    )


class Message(Base, IntPKMixin):
    __tablename__ = "messages"

    conversation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, comment="所属对话"
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), nullable=False, comment="user/assistant/system")
    content: Mapped[str] = mapped_column(LONGTEXT, nullable=False, comment="消息内容")
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, comment="Token 消耗")
    processing_time_ms: Mapped[int] = mapped_column(Integer, default=0, comment="处理耗时(ms)")
    created_at: Mapped[str] = mapped_column(String(30), default="", comment="创建时间字符串")

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    citations: Mapped[list["MessageCitation"]] = relationship(
        "MessageCitation", back_populates="message", cascade="all, delete-orphan"
    )


class MessageCitation(Base, IntPKMixin):
    __tablename__ = "message_citations"

    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, comment="所属消息"
    )
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, comment="引用文档"
    )
    chunk_index: Mapped[int] = mapped_column(Integer, default=0, comment="分块索引")
    score: Mapped[float] = mapped_column(Float, default=0.0, comment="相关度分数")
    cited_text: Mapped[str | None] = mapped_column(Text, comment="引用原文片段")

    message: Mapped[Message] = relationship(back_populates="citations")
