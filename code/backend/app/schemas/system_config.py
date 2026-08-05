"""系统配置 Schema。"""

from pydantic import BaseModel, Field


class SystemConfigResponse(BaseModel):
    """系统配置响应。"""

    key: str
    value: str
    description: str | None
    updated_at: str


class SystemConfigUpdate(BaseModel):
    """更新配置请求。"""

    value: str = Field(..., max_length=500, description="配置值")
    description: str | None = Field(default=None, max_length=255, description="说明")
