"""API v1 路由聚合。"""

from fastapi import APIRouter

from app.api.v1 import (
    audit_logs,
    auth,
    conversations,
    documents,
    knowledge_bases,
    qa,
    system_configs,
    users,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户"])
api_router.include_router(knowledge_bases.router, prefix="/knowledge-bases", tags=["知识库"])
api_router.include_router(documents.router, prefix="/documents", tags=["文档"])
api_router.include_router(qa.router, prefix="/qa", tags=["问答"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["对话"])
api_router.include_router(audit_logs.router, prefix="/audit-logs", tags=["审计"])
api_router.include_router(system_configs.router, prefix="/system/configs", tags=["系统配置"])
