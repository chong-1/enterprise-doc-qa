"""认证 API —— 注册/登录/Token 刷新。"""

from fastapi import APIRouter

from app.core.dependencies import DB
from app.core.exceptions import success_response
from app.schemas.auth import LoginRequest, RefreshTokenRequest, RegisterRequest
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/register", summary="用户注册")
async def register(payload: RegisterRequest, db: DB) -> dict:
    """注册新用户（默认分配 viewer 角色）。"""
    service = AuthService(db)
    user = await service.register(payload.username, payload.email, payload.password)
    return success_response(UserResponse.from_user(user), "注册成功")


@router.post("/login", summary="用户登录")
async def login(payload: LoginRequest, db: DB) -> dict:
    """用户名/邮箱 + 密码登录，返回 JWT Token 对。"""
    service = AuthService(db)
    user = await service.login(payload.username, payload.password)
    return success_response(service.create_token_pair(user), "登录成功")


@router.post("/refresh", summary="刷新 Access Token")
async def refresh_token(payload: RefreshTokenRequest, db: DB) -> dict:
    """用 Refresh Token 换取新的 Token 对。"""
    service = AuthService(db)
    return success_response(await service.refresh(payload.refresh_token), "刷新成功")
