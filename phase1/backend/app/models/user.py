"""用户 & 角色 & 权限模型。"""

from sqlalchemy import Boolean, String, Table, Column, ForeignKey, BigInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, IntPKMixin

# ========== 关联表 ==========

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", BigInteger, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


# ========== 模型 ==========

class User(Base, IntPKMixin, TimestampMixin):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="用户名")
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, comment="邮箱")
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False, comment="密码哈希")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否激活")
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, comment="超管标记")

    roles: Mapped[list["Role"]] = relationship(secondary=user_roles, back_populates="users")


class Role(Base, IntPKMixin, TimestampMixin):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="角色名称")
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="角色编码")
    description: Mapped[str | None] = mapped_column(String(255), comment="描述")

    users: Mapped[list[User]] = relationship(secondary=user_roles, back_populates="roles")
    permissions: Mapped[list["Permission"]] = relationship(secondary=role_permissions, back_populates="roles")


class Permission(Base, IntPKMixin):
    __tablename__ = "permissions"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, comment="权限名称")
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, comment="权限编码 resource:action")
    description: Mapped[str | None] = mapped_column(String(255), comment="描述")

    roles: Mapped[list[Role]] = relationship(secondary=role_permissions, back_populates="permissions")
