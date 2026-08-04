"""文档模型。"""

from sqlalchemy import BigInteger, Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, IntPKMixin

import enum


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base, IntPKMixin, TimestampMixin):
    __tablename__ = "documents"

    kb_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, comment="所属知识库"
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False, comment="原始文件名")
    file_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="pdf/docx/xlsx/md/txt")
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, comment="文件大小(bytes)")
    storage_path: Mapped[str] = mapped_column(String(1000), default="", comment="存储路径")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, comment="分块数量")
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), default=DocumentStatus.PENDING, comment="处理状态"
    )
    error_message: Mapped[str | None] = mapped_column(Text, comment="失败原因")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment="软删除标记")
    deleted_at: Mapped[str | None] = mapped_column(String(30), default=None, comment="删除时间")

    knowledge_base: Mapped["KnowledgeBase"] = relationship(back_populates="documents")
