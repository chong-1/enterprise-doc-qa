"""知识库 CRUD API。"""

from fastapi import APIRouter

router = APIRouter()


@router.post("")
async def create_knowledge_base():
    """创建知识库。"""
    pass


@router.get("")
async def list_knowledge_bases():
    """获取知识库列表。"""
    pass


@router.get("/{kb_id}")
async def get_knowledge_base():
    """获取知识库详情。"""
    pass


@router.put("/{kb_id}")
async def update_knowledge_base():
    """更新知识库。"""
    pass


@router.delete("/{kb_id}")
async def delete_knowledge_base():
    """删除知识库。"""
    pass
