"""LLM 后端基类：统一 chat / chat_stream 接口。"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass
class ChatMessage:
    role: str        # system / user / assistant
    content: str


class BaseLLMBackend(ABC):
    """LLM 抽象基类：支持普通调用和流式调用。"""

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """非流式对话，返回完整响应文本。"""
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """流式对话，逐 token yield。"""
        ...
