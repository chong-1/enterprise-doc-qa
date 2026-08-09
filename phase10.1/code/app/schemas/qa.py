"""问答相关 Schema。"""

from pydantic import BaseModel, Field


class QARequest(BaseModel):
    """问答请求。"""

    question: str = Field(min_length=1, max_length=5000, description="用户问题")
    conversation_id: int | None = Field(default=None, description="对话ID，不传则新建对话")
    stream: bool = Field(default=True, description="是否流式输出")
    agent_mode: bool = Field(default=False, description="是否启用 Agent 模式（Router + ReAct）")


class SourceCitation(BaseModel):
    """引用来源（简化版，直接用 retriever 返回的 metadata）。"""

    document: str = ""
    chunk_index: int = 0
    text: str = ""
    score: float = 0.0


class QANonStreamResponse(BaseModel):
    """问答响应（非流式）。"""

    answer: str
    conversation_id: int | None = None
    citations: list[SourceCitation] = []
    thought_chain: list[str] = []
    processing_time_ms: int = 0
    from_cache: bool = False


class ConversationResponse(BaseModel):
    """对话响应。"""

    id: int
    title: str
    kb_id: int | None
    message_count: int = 0
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    """消息响应。"""

    id: int
    role: str
    content: str
    tokens_used: int = 0
    citations: list[SourceCitation] = []
    created_at: str

    model_config = {"from_attributes": True}
