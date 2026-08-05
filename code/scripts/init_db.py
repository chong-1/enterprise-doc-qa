"""数据库初始化：创建所有表 + 默认数据。

使用方法：
    cd backend && python ../scripts/init_db.py
"""

import asyncio
import sys
from pathlib import Path

# 将 backend 目录加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.db.session import init_db, async_session_factory, close_db
from app.models.user import User, Role, Permission
from app.core.security import hash_password
from sqlalchemy import select


async def seed_default_data():
    """填充默认角色和权限。"""
    async with async_session_factory() as session:
        # 检查是否已有数据
        result = await session.execute(select(Role).limit(1))
        if result.scalar_one_or_none():
            print("[SKIP] 初始数据已存在")
            return

        # 创建权限
        perms = [
            Permission(name="文档上传", code="document:upload"),
            Permission(name="文档删除", code="document:delete"),
            Permission(name="文档查看", code="document:view"),
            Permission(name="知识库创建", code="kb:create"),
            Permission(name="知识库删除", code="kb:delete"),
            Permission(name="知识库管理", code="kb:manage"),
            Permission(name="问答查询", code="qa:ask"),
            Permission(name="用户管理", code="user:manage"),
            Permission(name="审计日志查看", code="audit:view"),
        ]
        session.add_all(perms)
        await session.flush()

        # 创建角色
        admin_role = Role(name="管理员", code="admin", description="系统管理员，拥有全部权限")
        editor_role = Role(name="编辑者", code="editor", description="可上传/管理文档和问答")
        viewer_role = Role(name="查看者", code="viewer", description="仅可查看文档和问答")

        admin_role.permissions = perms
        editor_role.permissions = [p for p in perms if p.code in {
            "document:upload", "document:delete", "document:view",
            "kb:create", "qa:ask",
        }]
        viewer_role.permissions = [p for p in perms if p.code in {
            "document:view", "qa:ask",
        }]

        session.add_all([admin_role, editor_role, viewer_role])
        await session.flush()

        # 创建默认管理员
        admin = User(
            username="admin",
            email="admin@enterprise-qa.local",
            hashed_password=hash_password("admin123456"),
            is_superuser=True,
        )
        admin.roles = [admin_role]
        session.add(admin)

        await session.commit()
        print("[OK] 初始数据创建完成")
        print("   管理员账号: admin / admin123456")


async def main():
    print("创建数据库表...")
    await init_db()
    print("[OK] 表创建完成")

    print("填充默认数据...")
    await seed_default_data()

    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
