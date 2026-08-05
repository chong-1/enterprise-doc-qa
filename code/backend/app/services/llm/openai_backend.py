"""OpenAI 兼容后端（支持 OpenAI / DeepSeek / Qwen 等兼容 API）。"""

import os
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.core.config import settings
from app.services.llm.base import BaseLLMBackend, ChatMessage


def _sanitize_ssl_cert_file() -> None:
    """清理无效的 SSL_CERT_FILE。

    conda activate 在 Windows (Git Bash) 下会把 SSL_CERT_FILE 指向
    <env>/ssl/cacert.pem（实际证书在 <env>/Library/ssl/cacert.pem），
    httpx 初始化时 ssl.create_default_context(cafile=...) 因文件不存在抛
    FileNotFoundError，导致所有 LLM 调用 500。删除后 httpx 回退到 certifi 证书。
    """
    cafile = os.environ.get("SSL_CERT_FILE")
    if cafile and not os.path.exists(cafile):
        del os.environ["SSL_CERT_FILE"]


class OpenAICompatibleBackend(BaseLLMBackend):
    """OpenAI / DeepSeek 兼容后端。"""

    def __init__(self) -> None:
        _sanitize_ssl_cert_file()
        self._client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )
        self._model = settings.LLM_MODEL
        self._default_max_tokens = settings.LLM_MAX_TOKENS
        self._default_temperature = settings.LLM_TEMPERATURE
        # 运行时模型覆盖（Phase 7 系统配置 llm.model 优先于 .env）
        self.override_model: str | None = None

    def _resolve_model(self) -> str:
        return self.override_model or self._model

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        response = await self._client.chat.completions.create(
            model=self._resolve_model(),
            messages=[{"role": m.role, "content": m.content} for m in messages],
            max_tokens=max_tokens or self._default_max_tokens,
            temperature=temperature if temperature is not None else self._default_temperature,
            stream=False,
        )
        return response.choices[0].message.content or ""

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self._resolve_model(),
            messages=[{"role": m.role, "content": m.content} for m in messages],
            max_tokens=max_tokens or self._default_max_tokens,
            temperature=temperature if temperature is not None else self._default_temperature,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
