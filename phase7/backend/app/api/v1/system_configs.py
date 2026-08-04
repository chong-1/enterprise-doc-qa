"""系统配置 API（仅管理员）：查看/修改全局配置。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.dependencies import DB, CurrentUser, require_admin
from app.core.exceptions import success_response
from app.models.user import User
from app.schemas.system_config import SystemConfigResponse, SystemConfigUpdate
from app.services import audit_service, system_config_service
from app.services.audit_service import client_ip

router = APIRouter()

#: 支持的业务配置键（修改后运行时生效，无需重启）
SUPPORTED_KEYS = {
    "llm.model": "LLM 模型名（如 deepseek-v4-flash）",
    "llm.temperature": "LLM 采样温度 (0-2)",
    "llm.max_tokens": "LLM 最大生成长度",
    "rag.top_k": "检索后送入 LLM 的候选数",
    "rag.max_chars": "上下文单条上限字符数",
}


@router.get("", summary="配置列表（管理员）")
async def list_configs(
    db: DB,
    _: Annotated[User, Depends(require_admin)],
):
    """列出全部系统配置 + 支持的配置项说明。"""
    configs = await system_config_service.list_configs(db)
    items = [
        SystemConfigResponse(
            key=c.key, value=c.value, description=c.description, updated_at=c.updated_at
        )
        for c in configs
    ]
    return success_response({"configs": items, "supported_keys": SUPPORTED_KEYS})


@router.put("/{key}", summary="更新配置（管理员）")
async def update_config(
    key: str,
    body: SystemConfigUpdate,
    db: DB,
    admin: CurrentUser,
    request: Request,
    _: Annotated[User, Depends(require_admin)],
):
    """写入配置值（30s 内全局生效）。"""
    if key not in SUPPORTED_KEYS:
        return success_response(
            {"error": f"不支持的配置键 {key}，可选: {list(SUPPORTED_KEYS)}"}
        )
    cfg = await system_config_service.set_config(
        db, key, body.value, body.description or SUPPORTED_KEYS[key]
    )
    await audit_service.log_action(
        db, admin, "config:update", "config", cfg.id,
        {"key": key, "value": body.value},
        client_ip(request),
    )
    return success_response(
        SystemConfigResponse(
            key=cfg.key, value=cfg.value, description=cfg.description, updated_at=cfg.updated_at
        ),
        message="配置已更新（30s 内生效）",
    )
