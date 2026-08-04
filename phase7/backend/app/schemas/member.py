"""知识库成员相关 Schema。"""

from pydantic import BaseModel, Field

from app.models.knowledge_base import KBMemberRole


class KBMemberCreate(BaseModel):
    """添加成员请求。"""

    user_id: int = Field(..., gt=0, description="用户ID")
    role: KBMemberRole = Field(default=KBMemberRole.VIEWER, description="角色: viewer/editor/owner")


class KBMemberUpdate(BaseModel):
    """修改成员角色请求。"""

    role: KBMemberRole = Field(..., description="新角色")


class KBMemberResponse(BaseModel):
    """成员响应。"""

    user_id: int
    username: str
    role: str
