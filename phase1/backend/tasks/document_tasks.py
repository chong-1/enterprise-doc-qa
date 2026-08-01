"""文档处理异步任务。"""

from tasks.celery_app import celery_app


# ====== TODO: Phase 3 实现 ======
@celery_app.task(bind=True, max_retries=3)
def process_document(self, document_id: int):
    """处理文档：解析 → 清洗 → 分块 → Embedding → 入库。"""
    pass
