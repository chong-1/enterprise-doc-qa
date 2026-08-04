"""创建管理员用户（Phase 7 用户管理后台）。

用法：
    python scripts/create_admin.py
    python scripts/create_admin.py --username admin --password Admin123456
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import async_session_factory
from app.models.user import User


async def main(username: str, email: str, password: str) -> None:
    async with async_session_factory() as db:
        exists = (
            await db.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if exists:
            print(f"用户 {username} 已存在，跳过")
            return
        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            is_superuser=True,
        )
        db.add(user)
        await db.commit()
        print(f"✅ 管理员 {username} 创建成功（is_superuser=True）")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="创建管理员用户")
    parser.add_argument("--username", default="admin", help="用户名")
    parser.add_argument("--email", default="admin@eqa.local", help="邮箱")
    parser.add_argument("--password", default="Admin123456", help="密码")
    args = parser.parse_args()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main(args.username, args.email, args.password))
    finally:
        loop.close()
