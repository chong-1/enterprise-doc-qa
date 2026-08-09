"""文档处理异步任务：解析 → 清洗 → 分块 → Embedding → Chroma 入库。

状态机：pending → processing → completed / failed
幂等：任务开头检查 completed 则直接返回（重复派发无害）
失败：标记 failed + 指数退避自动重试（最多 3 次）
"""

import asyncio

from sqlalchemy import select

from tasks.celery_app import celery_app
from app.db import chroma_store
from app.db.session import async_session_factory
from app.models.document import Document, DocumentStatus
from app.models.knowledge_base import KnowledgeBase
from app.services.document.chunker import split_text_into_chunks
from app.services.document.loader import read_file
from app.services.document.parser import clean_text, parse_document
from app.services.rag.embedding import encode


_worker_loop: asyncio.AbstractEventLoop | None = None


def _get_worker_loop() -> asyncio.AbstractEventLoop:
    """进程级单例事件循环。

    不能用 asyncio.run()：它每次创建并关闭新 loop，而 SQLAlchemy async 连接池
    跨任务复用连接，复用时会命中已关闭的旧 loop（Windows Proactor 下报
    AttributeError: 'NoneType' has no attribute 'send'）。
    单例 loop 贯穿所有任务，连接池始终绑定同一 loop。
    """
    global _worker_loop
    if _worker_loop is None:
        _worker_loop = asyncio.new_event_loop()
    return _worker_loop


@celery_app.task(bind=True, max_retries=3)
def process_document(self, document_id: int) -> None:
    """处理文档：解析 → 清洗 → 分块 → 更新状态。Celery 同步入口。"""
    _get_worker_loop().run_until_complete(_process_document(self, document_id))


async def _process_document(task, document_id: int) -> None:
    """任务核心逻辑（async 版本）。"""
    async with async_session_factory() as db:
        stmt = (
            select(Document, KnowledgeBase)
            .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
            .where(Document.id == document_id)
        )
        row = (await db.execute(stmt)).one_or_none()
        if row is None:
            return  # 文档已被删除，无事可做
        doc, kb = row
        if doc.status == DocumentStatus.COMPLETED:
            return  # 幂等：已完成不再重复处理

        # pending / processing / failed 均可进入处理
        doc.status = DocumentStatus.PROCESSING
        doc.error_message = None
        await db.commit()

    try:
        content = read_file(doc.storage_path)
        raw_text = parse_document(content, doc.file_type)
        text = clean_text(raw_text)
        chunks = split_text_into_chunks(text, kb.chunk_size, kb.chunk_overlap)

        # Phase 4：生成 Embedding 并写入 Chroma
        if chunks:
            chunk_texts = [c.text for c in chunks]
            # embedding 是 CPU 密集同步操作，放线程池避免阻塞 event loop
            vectors = await asyncio.to_thread(encode, chunk_texts)
            chroma_store.add_chunks(
                kb_id=kb.id,
                chunk_texts=chunk_texts,
                dense_vectors=[v["dense"] for v in vectors],
                metadatas=[
                    {
                        "doc_id": str(document_id),
                        "filename": doc.filename,
                        "chunk_idx": c.index,
                        "char_start": c.char_start,
                        "char_end": c.char_end,
                    }
                    for c in chunks
                ],
                chunk_ids=[f"doc_{document_id}_chunk_{c.index}" for c in chunks],
            )

        async with async_session_factory() as db:
            result = await db.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc is None:
                return
            doc.chunk_count = len(chunks)
            doc.status = DocumentStatus.COMPLETED
            doc.error_message = None
            await db.commit()
        # 文档变更 → 清空该 KB 的答案缓存，防止缓存答案过时
        from app.services.rag.query_cache import clear_kb_cache_sync
        clear_kb_cache_sync(doc.kb_id)
    except Exception as exc:
        # 标记失败（错误信息入库），再按指数退避重试
        async with async_session_factory() as db:
            result = await db.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc is not None:
                doc.status = DocumentStatus.FAILED
                doc.error_message = str(exc)[:2000]
                await db.commit()
        raise task.retry(exc=exc, countdown=60 * (2**task.request.retries))
