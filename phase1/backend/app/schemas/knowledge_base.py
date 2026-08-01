"""知识库相关 Schema。"""

from datetime import datetime

from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    """创建知识库请求。"""

    name: str = Field(min_length=1, max_length=200, description="知识库名称")
    description: str | None = Field(default=None, description="描述")
    embedding_model: str = Field(default="BAAI/bge-m3", description="Embedding 模型")
    chunk_size: int = Field(default=512, ge=128, le=2048, description="分块大小")
    chunk_overlap: int = Field(default=64, ge=0, le=512, description="分块重叠")
    is_public: bool = Field(default=False, description="是否公开")


class KnowledgeBaseUpdate(BaseModel):
    """更新知识库请求。"""

    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    is_public: bool | None = None


class KnowledgeBaseResponse(BaseModel):
    """知识库响应。"""

    id: int
    name: str
    description: str | None
    owner_id: int
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    is_public: bool
    document_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
