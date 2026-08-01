"""SQLAlchemy Base + 通用 Mixin。"""

from datetime import datetime

from sqlalchemy import DateTime, BigInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""
    pass


class TimestampMixin:
    """创建时间 + 更新时间 Mixin。

    使用 Python 侧默认值而非 SQL 侧 default=func.now()：
    async 会话下 SQL 侧默认值会在 flush 后标记列为 expired，
    序列化时访问触发 lazy load 导致 MissingGreenlet 错误。
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="更新时间"
    )


class IntPKMixin:
    """自增整数主键 Mixin。"""

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
