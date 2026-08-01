"""知识库模型。"""

from sqlalchemy import Boolean, BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, IntPKMixin


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
