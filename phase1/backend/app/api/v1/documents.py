"""文档上传 & 管理 API。"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/upload")
async def upload_document():
    """上传文档到指定知识库。"""
    pass


@router.get("/{doc_id}/status")
async def get_document_status():
    """查询文档处理状态。"""
    pass


@router.delete("/{doc_id}")
async def delete_document():
    """删除文档。"""
    pass
