"""文档上传 & 管理 API。"""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.dependencies import DB, require_permission
from app.core.exceptions import BadRequestError, NotFoundError, success_response
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.schemas.document import DocumentResponse, DocumentStatusResponse
from app.services.document.loader import delete_file, save_file
from app.services.document.parser import SUPPORTED_FILE_TYPES
from tasks.document_tasks import process_document

router = APIRouter()

# 单文件大小上限：50MB
MAX_UPLOAD_SIZE = 50 * 1024 * 1024


@router.post("/upload")
async def upload_document(
    db: DB,
    _: Annotated[User, Depends(require_permission("document:upload"))],
    kb_id: int = Form(..., description="目标知识库 ID"),
    file: UploadFile = File(..., description="上传文件"),
):
    """上传文档到指定知识库（异步处理，返回后轮询状态）。"""
    # 1. 校验知识库存在
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise NotFoundError(f"知识库 {kb_id} 不存在")

    # 2. 校验文件名与类型
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED_FILE_TYPES:
        raise BadRequestError(
            f"不支持的文件类型: {ext or '无扩展名'}，仅支持 {', '.join(sorted(SUPPORTED_FILE_TYPES))}"
        )

    # 3. 读取内容并校验大小
    content = await file.read()
    if not content:
        raise BadRequestError("文件内容为空")
    if len(content) > MAX_UPLOAD_SIZE:
        raise BadRequestError(f"文件大小超过上限 {MAX_UPLOAD_SIZE // 1024 // 1024}MB")

    # 4. 保存文件 + 写库（pending）
    storage_path = save_file(content, filename)
    doc = Document(
        kb_id=kb_id,
        filename=filename,
        file_type=ext,
        file_size=len(content),
        storage_path=storage_path,
    )
    db.add(doc)
    await db.flush()

    # 5. 派发 Celery 异步处理（同步派发会阻塞事件循环，放线程池）
    await asyncio.to_thread(process_document.delay, doc.id)

    return success_response(DocumentResponse.model_validate(doc), message="上传成功，正在异步解析")


@router.get("/{doc_id}/status")
async def get_document_status(
    doc_id: int,
    db: DB,
    _: Annotated[User, Depends(require_permission("document:view"))],
):
    """查询文档处理状态。"""
    doc = await db.get(Document, doc_id)
    if doc is None:
        raise NotFoundError(f"文档 {doc_id} 不存在")
    return success_response(
        DocumentStatusResponse(
            id=doc.id,
            filename=doc.filename,
            status=doc.status.value,
            chunk_count=doc.chunk_count,
            error_message=doc.error_message,
        )
    )


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: int,
    db: DB,
    _: Annotated[User, Depends(require_permission("document:delete"))],
):
    """删除文档（文件 + 数据库记录）。Chroma 级联删除在 Phase 7 完善。"""
    doc = await db.get(Document, doc_id)
    if doc is None:
        raise NotFoundError(f"文档 {doc_id} 不存在")
    delete_file(doc.storage_path)
    await db.delete(doc)
    return success_response(None, message="删除成功")
