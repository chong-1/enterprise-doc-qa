"""Embedding 生成异步任务。"""

from tasks.celery_app import celery_app


# ====== TODO: Phase 4 实现 ======
@celery_app.task(bind=True, max_retries=3)
def batch_embed(self, text_chunks: list[str]):
    """批量生成 Embedding 并存入 Chroma。"""
    pass
