"""SQLAlchemy Base + 通用 Mixin。"""

from datetime import datetime

from sqlalchemy import DateTime, BigInteger, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""
    pass


class TimestampMixin:
    """创建时间 + 更新时间 Mixin。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )


class IntPKMixin:
    """自增整数主键 Mixin。"""

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
