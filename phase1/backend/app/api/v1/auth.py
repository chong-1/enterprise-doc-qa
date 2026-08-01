"""认证 API —— 注册/登录/Token 刷新。"""

from fastapi import APIRouter

router = APIRouter()


# ====== TODO: Phase 2 实现 ======
@router.post("/register")
async def register():
    """用户注册。"""
    pass


@router.post("/login")
async def login():
    """用户登录。"""
    pass


@router.post("/refresh")
async def refresh_token():
    """刷新 Access Token。"""
    pass
