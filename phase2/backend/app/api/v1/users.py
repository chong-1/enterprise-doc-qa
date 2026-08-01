"""用户管理 API。"""

from fastapi import APIRouter

from app.core.dependencies import CurrentUser
from app.core.exceptions import success_response
from app.schemas.user import UserResponse

router = APIRouter()


@router.get("/me", summary="获取当前登录用户信息")
async def get_current_user_info(user: CurrentUser) -> dict:
    """返回当前用户信息（含角色列表）。"""
    return success_response(UserResponse.from_user(user))
