"""知识库模型。"""

import enum

from sqlalchemy import (
    Boolean,
    BigInteger,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, IntPKMixin


class KBMemberRole(str, enum.Enum):
    """知识库成员角色（权限从低到高）。"""

    VIEWER = "viewer"  # 可查看/问答
    EDITOR = "editor"  # + 上传/删除文档、编辑配置
    OWNER = "owner"  # + 成员管理、删除知识库


class KnowledgeBase(Base, IntPKMixin, TimestampMixin):
    __tablename__ = "knowledge_bases"

    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="知识库名称")
    description: Mapped[str | None] = mapped_column(Text, comment="描述")
    owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="创建者"
    )
    embedding_model: Mapped[str] = mapped_column(String(100), default="BAAI/bge-m3", comment="Embedding 模型")
    chunk_size: Mapped[int] = mapped_column(Integer, default=512, comment="分块大小(tokens)")
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=64, comment="分块重叠(tokens)")
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否公开")

    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="knowledge_base", cascade="all, delete-orphan"
    )
    members: Mapped[list["KnowledgeBaseMember"]] = relationship(
        "KnowledgeBaseMember",
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
    )


class KnowledgeBaseMember(Base, IntPKMixin):
    """知识库成员（owner 由 knowledge_bases.owner_id 表示，不重复入表）。"""

    __tablename__ = "kb_members"
    __table_args__ = (UniqueConstraint("kb_id", "user_id", name="uq_kb_member"),)

    kb_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, comment="知识库"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="成员"
    )
    role: Mapped[KBMemberRole] = mapped_column(
        Enum(KBMemberRole), default=KBMemberRole.VIEWER, nullable=False, comment="角色"
    )

    knowledge_base: Mapped[KnowledgeBase] = relationship(back_populates="members")
