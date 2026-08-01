"""全局配置管理（pydantic-settings）。"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


# backend/ 代码目录（config.py 位于 backend/app/core/，上溯三级）
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
# 项目根目录（含 .env）
_PROJECT_ROOT = _BACKEND_DIR.parent


class Settings(BaseSettings):
    """应用配置，自动从项目根目录的 .env 文件加载。"""

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="allow",
    )

    # ========== 应用 ==========
    APP_NAME: str = "EnterpriseQA"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me"
    API_PREFIX: str = "/api/v1"

    # ========== 项目路径 ==========
    BASE_DIR: Path = _BACKEND_DIR

    # ========== MySQL ==========
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "eqa_user"
    MYSQL_PASSWORD: str = "eqa_password_2024"
    MYSQL_DATABASE: str = "enterprise_qa"
    MYSQL_POOL_SIZE: int = 20
    MYSQL_POOL_RECYCLE: int = 3600

    @property
    def database_url(self) -> str:
        """构建异步 MySQL 连接字符串。"""
        return (
            f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            f"?charset=utf8mb4"
        )

    @property
    def sync_database_url(self) -> str:
        """同步连接字符串（Alembic 迁移用）。"""
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            f"?charset=utf8mb4"
        )

    # ========== Redis ==========
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    @property
    def redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ========== 文件存储 ==========
    STORAGE_TYPE: Literal["local", "minio"] = "local"
    LOCAL_STORAGE_DIR: str = "./data/uploads"
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "documents"
    MINIO_SECURE: bool = False

    # ========== Chroma ==========
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    CHROMA_COLLECTION_PREFIX: str = "kb_"

    # ========== Embedding ==========
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DEVICE: str = "cpu"
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_NORMALIZE: bool = True

    # ========== Reranker ==========
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"
    RERANKER_DEVICE: str = "cpu"
    RERANKER_TOP_K: int = 5

    # ========== LLM ==========
    LLM_BACKEND: Literal["openai", "ollama"] = "openai"
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str = "sk-your-api-key-here"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_MAX_TOKENS: int = 2048
    LLM_TEMPERATURE: float = 0.1

    # ========== JWT ==========
    JWT_SECRET_KEY: str = "jwt-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ========== Celery ==========
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ========== 分块 ==========
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64

    # ========== 限流 ==========
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_DAY: int = 1000

    # ========== CORS ==========
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    """获取配置单例。"""
    return Settings()


settings = get_settings()
