"""对话记忆管理（内存版，Phase 6 迁移到 Redis）。"""

from collections import defaultdict

from langchain_core.messages import BaseMessage

# { conversation_id: [messages] }
_store: dict[int, list[BaseMessage]] = defaultdict(list)

MAX_HISTORY = 10  # 最近 10 轮（user + assistant 各一条）


def get_history(conversation_id: int | None) -> list[BaseMessage]:
    """获取对话历史。"""
    if conversation_id is None:
        return []
    return _store.get(conversation_id, [])


def add_message(conversation_id: int, message: BaseMessage) -> None:
    """添加一条消息到对话历史。"""
    _store[conversation_id].append(message)
    # 只保留最近 MAX_HISTORY 对
    if len(_store[conversation_id]) > MAX_HISTORY * 2:
        _store[conversation_id] = _store[conversation_id][-(MAX_HISTORY * 2):]


def clear_history(conversation_id: int) -> None:
    """清除对话历史。"""
    _store.pop(conversation_id, None)
