"""用户相关 Schema。"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserResponse(BaseModel):
    """用户信息响应。"""

    id: int
    username: str
    email: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    roles: list[str] = Field(default_factory=list, description="角色编码列表")

    model_config = {"from_attributes": True}

    @classmethod
    def from_user(cls, user) -> "UserResponse":
        """从 ORM 用户模型构建响应（角色转换为编码列表）。"""
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            created_at=user.created_at,
            roles=[r.code for r in user.roles],
        )


class UserUpdateRequest(BaseModel):
    """更新用户信息请求。"""

    email: EmailStr | None = None
    password: str | None = None
