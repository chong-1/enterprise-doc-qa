"""文档上传 & 管理 API（Phase 7：知识库角色校验 + 软删除 + 审计）。"""

import asyncio
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy import select

from app.core.dependencies import DB, CurrentUser, check_kb_access
from app.core.exceptions import BadRequestError, NotFoundError, success_response
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.schemas.document import DocumentResponse, DocumentStatusResponse
from app.services import audit_service
from app.services.audit_service import client_ip
from app.services.document.loader import delete_file, save_file
from app.services.document.parser import SUPPORTED_FILE_TYPES
from tasks.document_tasks import process_document

router = APIRouter()

# 单文件大小上限：50MB
MAX_UPLOAD_SIZE = 50 * 1024 * 1024


@router.post("/upload")
async def upload_document(
    db: DB,
    user: CurrentUser,
    request: Request,
    kb_id: int = Form(..., description="目标知识库 ID"),
    file: UploadFile = File(..., description="上传文件"),
):
    """上传文档到指定知识库（editor 及以上，异步处理）。

    注意：kb_id 是 Form 字段而非路径参数，不能复用 require_kb_role 依赖，
    改为内联调用 check_kb_access。
    """
    # 0. 知识库级权限校验（editor 及以上）
    await check_kb_access(db, user, kb_id, "editor")
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
    await audit_service.log_action(
        db, user, "document:upload", "document", doc.id,
        {"kb_id": kb_id, "filename": filename, "size": len(content)},
        client_ip(request),
    )

    # 5. 派发 Celery 异步处理（同步派发会阻塞事件循环，放线程池）
    await asyncio.to_thread(process_document.delay, doc.id)

    return success_response(DocumentResponse.model_validate(doc), message="上传成功，正在异步解析")


@router.get("")
async def list_documents(
    kb_id: int,
    db: DB,
    user: CurrentUser,
    request: Request,
):
    """列出知识库文档（viewer 及以上，排除软删除）。"""
    await check_kb_access(db, user, kb_id, "viewer")
    stmt = (
        select(Document)
        .where(Document.kb_id == kb_id, Document.is_deleted.is_(False))
        .order_by(Document.id.desc())
    )
    result = await db.execute(stmt)
    return success_response([DocumentResponse.model_validate(d) for d in result.scalars().all()])


@router.get("/{doc_id}/status")
async def get_document_status(
    doc_id: int,
    db: DB,
    user: CurrentUser,
):
    """查询文档处理状态（viewer 及以上）。"""
    doc = await db.get(Document, doc_id)
    if doc is None or doc.is_deleted:
        raise NotFoundError(f"文档 {doc_id} 不存在")
    await check_kb_access(db, user, doc.kb_id, "viewer")
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
    user: CurrentUser,
    request: Request,
):
    """删除文档（editor 及以上）：软删除 + Chroma 级联删除 + 删除磁盘文件。"""
    doc = await db.get(Document, doc_id)
    if doc is None or doc.is_deleted:
        raise NotFoundError(f"文档 {doc_id} 不存在")
    await check_kb_access(db, user, doc.kb_id, "editor")

    # 1. Chroma 级联删除该文档的所有 chunk
    from app.db import chroma_store

    chroma_store.delete_chunks_by_doc(doc.kb_id, doc_id)
    # 2. 删除磁盘文件
    if doc.storage_path:
        delete_file(doc.storage_path)
    # 3. 数据库软删除
    doc.is_deleted = True
    doc.deleted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await audit_service.log_action(
        db, user, "document:delete", "document", doc_id,
        {"kb_id": doc.kb_id, "filename": doc.filename},
        client_ip(request),
    )
    return success_response(None, message="删除成功")
