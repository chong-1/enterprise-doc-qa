"""用户相关 Schema。"""

from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    """用户信息响应。"""

    id: int
    username: str
    email: str
    is_active: bool
    is_superuser: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    """更新用户信息请求。"""

    email: EmailStr | None = None
    password: str | None = None
