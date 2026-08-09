"""OpenAI 兼容后端（支持 OpenAI / DeepSeek / Qwen 等兼容 API）。"""

import asyncio
import os
import random
from collections.abc import AsyncIterator

from openai import AsyncOpenAI, RateLimitError

from app.core.config import settings
from app.services.llm.base import BaseLLMBackend, ChatMessage
from app.services.llm.rate_limit import TokenBucket


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
        # 高并发优化（双层限流，防 API 429）：
        # - 令牌桶：限制"每秒发送"速率（须低于 API 配额，主动不触发 429）
        # - 信号量：限制"同时在途"数量（防长请求堆积时新请求涌入）
        self._bucket = TokenBucket(settings.LLM_RATE_PER_SECOND, settings.LLM_BURST_CAPACITY)
        self._semaphore = asyncio.Semaphore(settings.LLM_MAX_CONCURRENCY)

    def _resolve_model(self) -> str:
        return self.override_model or self._model

    async def _create_with_retry(self, **kwargs):
        """调用 API（429 重试：尊重 Retry-After + 指数退避 + 随机抖动防雪崩）。

        仅在请求创建阶段重试（流式中途断开不重试——需重放全部消息且用户已见部分输出）。
        """
        for attempt in range(settings.LLM_RETRY_MAX):
            try:
                return await self._client.chat.completions.create(**kwargs)
            except RateLimitError as exc:
                if attempt >= settings.LLM_RETRY_MAX - 1:
                    raise  # 最后一次仍 429，抛给上层
                # 1) 优先尊重服务端 Retry-After 头
                wait: float | None = None
                response = getattr(exc, "response", None)
                if response is not None:
                    retry_after = response.headers.get("Retry-After")
                    try:
                        wait = float(retry_after)
                    except (TypeError, ValueError):
                        wait = None
                # 2) 无头则指数退避：base → base*2 → base*4
                if wait is None:
                    wait = settings.LLM_RETRY_BASE_DELAY * (2**attempt)
                # 3) 随机抖动：防止多个请求同时重试造成雪崩
                wait += random.uniform(0, 0.5)
                await asyncio.sleep(wait)

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        await self._bucket.acquire()  # 令牌桶限速率
        async with self._semaphore:   # 信号量限在途
            response = await self._create_with_retry(
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
        await self._bucket.acquire()  # 令牌桶限速率
        # 信号量覆盖整个流式生命周期（流期间持续占用 API 配额）
        async with self._semaphore:
            stream = await self._create_with_retry(
                model=self._resolve_model(),
                messages=[{"role": m.role, "content": m.content} for m in messages],
                max_tokens=max_tokens or self._default_max_tokens,
                temperature=temperature if temperature is not None else self._default_temperature,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
