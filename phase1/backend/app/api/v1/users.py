"""用户管理 API。"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/me")
async def get_current_user():
    """获取当前登录用户信息。"""
    pass
