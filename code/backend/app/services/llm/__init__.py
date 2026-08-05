"""LLM 后端工厂。"""

from app.core.config import settings
from app.services.llm.base import BaseLLMBackend
from app.services.llm.openai_backend import OpenAICompatibleBackend


def get_llm_backend() -> BaseLLMBackend:
    """根据配置返回 LLM 后端实例。"""
    if settings.LLM_BACKEND == "openai":
        return OpenAICompatibleBackend()
    # ollama 后端 Phase 10 扩展
    raise ValueError(f"不支持的 LLM 后端: {settings.LLM_BACKEND}")
