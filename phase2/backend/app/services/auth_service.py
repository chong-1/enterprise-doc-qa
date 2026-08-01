"""认证服务：注册、登录、Token 签发与刷新。"""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import Role, User
from app.schemas.auth import TokenResponse


class AuthService:
    """处理用户注册、登录与 Token 签发/刷新。

    不持有状态，数据库会话通过构造函数注入。
    """

    #: 新注册用户的默认角色（最小权限）
    DEFAULT_ROLE_CODE = "viewer"

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, username: str, email: str, password: str) -> User:
        """注册新用户，默认分配 viewer 角色。"""
        stmt = select(User).where(
            or_(User.username == username, User.email == email)
        )
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise ConflictError("用户名或邮箱已存在")

        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
        )

        # 分配默认角色（角色表未初始化时跳过，不影响注册）
        role_result = await self.db.execute(
            select(Role).where(Role.code == self.DEFAULT_ROLE_CODE)
        )
        viewer_role = role_result.scalar_one_or_none()
        if viewer_role:
            user.roles = [viewer_role]

        self.db.add(user)
        await self.db.flush()
        return user

    async def login(self, identifier: str, password: str) -> User:
        """用户名/邮箱 + 密码登录，校验通过返回用户。"""
        stmt = select(User).where(
            or_(User.username == identifier, User.email == identifier)
        )
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None or not verify_password(password, user.hashed_password):
            raise UnauthorizedError("用户名或密码错误")
        if not user.is_active:
            raise UnauthorizedError("账号已被禁用")

        return user

    def create_token_pair(self, user: User) -> TokenResponse:
        """为用户签发 Access + Refresh Token 对。"""
        return TokenResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )

    async def refresh(self, refresh_token: str) -> TokenResponse:
        """校验 Refresh Token，签发新的 Token 对。"""
        payload = decode_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise UnauthorizedError("Refresh Token 无效或已过期")

        try:
            user_id = int(payload["sub"])
        except (ValueError, KeyError):
            raise UnauthorizedError("Refresh Token 格式错误")

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise UnauthorizedError("用户不存在或已被禁用")

        return self.create_token_pair(user)
