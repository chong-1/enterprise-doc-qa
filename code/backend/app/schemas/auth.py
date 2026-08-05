"""认证相关 Schema。"""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """注册请求。"""

    username: str = Field(min_length=2, max_length=50, description="用户名")
    email: EmailStr = Field(description="邮箱")
    password: str = Field(min_length=6, max_length=128, description="密码")


class LoginRequest(BaseModel):
    """登录请求。"""

    username: str = Field(description="用户名或邮箱")
    password: str = Field(description="密码")


class TokenResponse(BaseModel):
    """Token 响应。"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """刷新 Token 请求。"""

    refresh_token: str
