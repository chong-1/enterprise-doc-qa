"""测试数据填充：创建示例知识库和文档。

使用方法：
    cd backend && python ../scripts/seed_data.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.db.session import async_session_factory
from app.models.knowledge_base import KnowledgeBase
from app.models.document import Document, DocumentStatus
from sqlalchemy import select


async def seed():
    async with async_session_factory() as session:
        # 检查是否已存在
        result = await session.execute(
            select(KnowledgeBase).where(KnowledgeBase.name == "示例知识库")
        )
        if result.scalar_one_or_none():
            print("[SKIP] 测试数据已存在")
            return

        # 创建示例知识库
        kb = KnowledgeBase(
            name="示例知识库",
            description="用于测试的知识库，包含常见文档类型",
            owner_id=1,
            is_public=True,
        )
        session.add(kb)
        await session.flush()

        print(f"[OK] 示例知识库创建完成 (id={kb.id})")
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
