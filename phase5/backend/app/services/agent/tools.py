"""Agent 工具集：Agent 可调用的函数。

LangChain @tool 装饰器将函数包装为 LangChain Tool。
注意：工具可能从 LangGraph 的 async 上下文中调用，此时不能用 asyncio.run()。
"""

import asyncio

from langchain_core.tools import tool


def _run_async(coro):
    """兼容同步和异步上下文的 async 执行器。"""
    try:
        loop = asyncio.get_running_loop()
        # 已有运行中的 loop → nest_asyncio 嵌套
        import nest_asyncio
        nest_asyncio.apply(loop)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@tool
def search_knowledge_base(query: str, kb_id: int) -> str:
    """搜索知识库，返回相关文档片段。用于回答用户关于文档内容的问题。

    Args:
        query: 搜索查询文本
        kb_id: 知识库 ID
    """
    from app.services.rag import retriever

    candidates = retriever.hybrid_search(kb_id, query)
    if not candidates:
        return "未找到相关文档内容。"
    parts = []
    for i, c in enumerate(candidates[:5], 1):
        meta = c.get("metadata", {})
        src = meta.get("filename", "未知")
        parts.append(f"[来源{i}] {src}\n{c['text'][:500]}")
    return "\n\n".join(parts)


@tool
def list_documents(kb_id: int) -> str:
    """列出知识库中的所有文档（仅元数据）。用于了解知识库里有哪些文件。"""
    from app.db.session import async_session_factory
    from app.models.document import Document
    from sqlalchemy import select

    async def _list():
        async with async_session_factory() as db:
            result = await db.execute(
                select(Document).where(Document.kb_id == kb_id)
            )
            docs = result.scalars().all()
            if not docs:
                return "知识库中暂无文档。"
            return "\n".join(
                f"  ID={d.id} | {d.filename} | {d.file_type} | {d.status.value} | {d.chunk_count} chunks"
                for d in docs
            )
    return _run_async(_list())


@tool
def get_document_info(doc_id: int) -> str:
    """获取指定文档的详细信息。用于查看某个文档的具体内容。"""
    from app.db.session import async_session_factory
    from app.models.document import Document

    async def _get():
        async with async_session_factory() as db:
            doc = await db.get(Document, doc_id)
            if not doc:
                return f"文档 {doc_id} 不存在。"
            return (
                f"文档 ID: {doc.id}\n文件名: {doc.filename}\n"
                f"类型: {doc.file_type}\n大小: {doc.file_size} bytes\n"
                f"分块数: {doc.chunk_count}\n状态: {doc.status.value}"
            )
    return _run_async(_get())


AGENT_TOOLS = [search_knowledge_base, list_documents, get_document_info]
