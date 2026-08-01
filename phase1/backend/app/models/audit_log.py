"""审计日志模型。"""

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IntPKMixin


class AuditLog(Base, IntPKMixin):
    __tablename__ = "audit_logs"

    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="操作人"
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False, comment="操作类型: upload/delete/query/create等")
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="资源类型: document/kb/user")
    resource_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="资源ID")
    detail: Mapped[str | None] = mapped_column(Text, comment="操作详情(JSON)")
    ip_address: Mapped[str | None] = mapped_column(String(50), comment="操作IP")
    created_at: Mapped[str] = mapped_column(String(30), default="", comment="操作时间")
