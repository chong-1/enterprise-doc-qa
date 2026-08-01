"""Celery 应用配置。"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "enterprise_qa",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["tasks.document_tasks", "tasks.embedding_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=600,   # 10 分钟软超时
    task_time_limit=900,        # 15 分钟硬超时
    task_default_retry_delay=60,
    task_max_retries=3,
)
