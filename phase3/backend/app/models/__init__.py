"""SQLAlchemy ORM 模型 —— 纯表定义，不含业务方法。

聚合导入所有模型：确保 Base.metadata 完整，
init_db 的 create_all 与 Alembic autogenerate 都能感知全部表。
"""

from app.models.base import Base, IntPKMixin, TimestampMixin
from app.models.user import Permission, Role, User, role_permissions, user_roles
from app.models.knowledge_base import KnowledgeBase
from app.models.document import Document, DocumentStatus
from app.models.conversation import Conversation, Message, MessageCitation, MessageRole
from app.models.audit_log import AuditLog

__all__ = [
    "Base",
    "IntPKMixin",
    "TimestampMixin",
    "User",
    "Role",
    "Permission",
    "user_roles",
    "role_permissions",
    "KnowledgeBase",
    "Document",
    "DocumentStatus",
    "Conversation",
    "Message",
    "MessageCitation",
    "MessageRole",
    "AuditLog",
]
