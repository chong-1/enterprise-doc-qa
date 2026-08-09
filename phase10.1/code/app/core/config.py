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
    # 公网跨云连接易被中间设备静默断开，10 分钟主动回收空闲连接
    MYSQL_POOL_RECYCLE: int = 600

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
    def redis_base_url(self) -> str:
        """Redis 基础连接串（不含 DB 号）。"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}"

    @property
    def redis_url(self) -> str:
        """Redis 完整连接串（默认 DB 0）。"""
        return f"{self.redis_base_url}/{self.REDIS_DB}"

    # ========== 文件存储 ==========
    LOCAL_STORAGE_DIR: str = "./data/uploads"

    # ========== Chroma ==========
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    CHROMA_COLLECTION_PREFIX: str = "kb_"

    # ========== Embedding ==========
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DEVICE: str = "cpu"
    # HuggingFace 下载镜像 + 缓存目录（C 盘空间有限，缓存模型到 D 盘）
    HF_ENDPOINT: str = "https://hf-mirror.com"
    HF_HOME: str = "D:/huggingface"
    EMBEDDING_BATCH_SIZE: int = 32

    # ========== LLM ==========
    LLM_BACKEND: Literal["openai", "ollama"] = "openai"
    LLM_BASE_URL: str = "https://api.deepseek.com"
    # API Key 必须从 .env 的 LLM_API_KEY 注入，代码库中不留默认密钥
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-v4-flash"
    LLM_MAX_TOKENS: int = 2048
    LLM_TEMPERATURE: float = 0.1

    # ========== JWT ==========
    JWT_SECRET_KEY: str = "jwt-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ========== Celery ==========
    @property
    def celery_broker_url(self) -> str:
        """Celery Broker（跟随 REDIS_HOST 动态构造，DB 1）。"""
        return f"{self.redis_base_url}/1"

    @property
    def celery_result_backend(self) -> str:
        """Celery Result Backend（DB 2）。"""
        return f"{self.redis_base_url}/2"

    # ========== 分块 ==========
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64

    # ========== 高并发优化 ==========
    QA_CACHE_ENABLED: bool = True     # 答案缓存总开关
    QA_CACHE_TTL: int = 86400         # 答案缓存 TTL（秒，默认 24h）
    QUERY_EMB_CACHE_TTL: int = 86400  # query 向量缓存 TTL（秒）
    LLM_MAX_CONCURRENCY: int = 5      # LLM 最大在途并发（防 API 429，超出排队）

    # ========== LLM 限流（令牌桶 + 429 重试） ==========
    LLM_RATE_PER_SECOND: float = 5.0    # 令牌桶补充速率（请求/秒，须低于 API 配额）
    LLM_BURST_CAPACITY: float = 10.0    # 令牌桶容量（允许的最大突发请求数）
    LLM_RETRY_MAX: int = 3              # 429 最大重试次数
    LLM_RETRY_BASE_DELAY: float = 1.0   # 429 重试基础退避（秒，指数增长 1s/2s/4s）

    # ========== 限流 ==========
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_PER_MINUTE: int = 60

    # ========== CORS ==========
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    """获取配置单例。"""
    return Settings()


settings = get_settings()
