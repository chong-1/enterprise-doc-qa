"""系统配置模型（键值对，管理端可改，运行时生效）。"""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IntPKMixin


class SystemConfig(Base, IntPKMixin):
    __tablename__ = "system_configs"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, comment="配置键")
    value: Mapped[str] = mapped_column(String(500), default="", comment="配置值(字符串)")
    description: Mapped[str | None] = mapped_column(String(255), comment="说明")
    updated_at: Mapped[str] = mapped_column(String(30), default="", comment="更新时间")
