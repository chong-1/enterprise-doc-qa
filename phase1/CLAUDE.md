# CLAUDE.md

企业文档智能问答平台的项目级行为规范，定义架构边界、编码约定和开发工作流。会话中优先遵循此文件，其次遵循全局 `~/.claude/CLAUDE.md`。

---

## 1. 项目概述

基于 RAG + Multi-Agent 的企业文档智能问答系统，支持多格式文档解析、混合检索、Agent 编排和流式对话。

| 层 | 技术 |
|---|---|
| 后端框架 | Python 3.12 + FastAPI + Pydantic v2 |
| 关系数据库 | MySQL 8.0 + SQLAlchemy 2.0 (async) + aiomysql |
| 数据库迁移 | Alembic |
| 向量数据库 | Chroma (PersistentClient, 本地持久化) |
| Embedding | BGE-M3 (dense 1024d + sparse 词汇权重) |
| Reranker | BGE-Reranker-v2-m3 |
| LLM | OpenAI 兼容接口 / Ollama 本地，双后端可切换 |
| 异步任务 | Celery + Redis Broker |
| 缓存/会话 | Redis 7.x |
| 对象存储 | MinIO（开发期可选本地文件系统） |
| Agent 框架 | LangGraph |
| OCR | PaddleOCR |
| 容器化 | Docker Compose |
| 前端 | Vue 3 + Element Plus (可选) |

---

## 2. 架构边界（不可逾越）

### 2.1 目录职责

```
backend/app/
├── api/v1/          # 仅薄路由层：参数校验 → 调用 service → 返回响应
├── core/            # 全局配置/安全/依赖注入/异常（不包含业务逻辑）
├── models/          # SQLAlchemy ORM 模型（纯表定义，不含业务方法）
├── schemas/         # Pydantic 请求/响应模型（与 API 一一对应）
├── services/        # 核心业务逻辑（所有领域逻辑在此）
│   ├── document/    # 文档解析、分块、上传
│   ├── rag/         # Embedding、检索、重排、生成
│   ├── agent/       # Agent 路由、工具、状态图
│   └── llm/         # LLM 后端封装
├── db/              # 数据库会话、向量库、Redis 工具封装
└── middleware/       # CORS/日志/限流
```

### 2.2 依赖方向（严格单向）

```
api → schemas, services, core
services → models, db, schemas
db → models
core ← 被所有模块依赖
```

- **禁止**：api 直接操作 models（必须通过 services）
- **禁止**：services 之间循环引用
- **禁止**：models 引用 services 或 api
- **允许**：services 内部互调（通过 `__init__.py` 统一导出）

### 2.3 异步边界

- **所有 API 端点**必须是 `async def`
- **所有数据库操作**使用 SQLAlchemy async session
- **所有 LLM 调用**使用 `httpx.AsyncClient`
- **Chroma 操作**使用同步客户端（Chroma 暂不支持原生 async），在 `run_in_executor` 中执行
- **Celery 任务**是同步函数（Celery worker 在独立进程中运行）

---

## 3. 编码规范

### 3.1 命名约定

| 类型 | 规范 | 示例 |
|---|---|---|
| 文件名 | snake_case | `knowledge_base.py` |
| 类名 | PascalCase | `KnowledgeBaseService` |
| 函数/方法 | snake_case | `def search_documents()` |
| 变量 | snake_case | `chunk_count` |
| 常量 | UPPER_SNAKE | `MAX_CHUNK_SIZE` |
| 数据库表 | 复数 snake_case | `knowledge_bases` |
| API 路由 | kebab-case (URL) | `/api/v1/knowledge-bases` |
| 环境变量 | UPPER_SNAKE | `MYSQL_HOST` |

### 3.2 类型注解

- **所有函数签名**必须有完整类型注解（参数 + 返回值）
- 使用 Pydantic 模型做运行时校验，不依赖类型注解做校验
- 数据库模型使用 `Mapped[T]` + `mapped_column()` (SQLAlchemy 2.0 风格)

```python
# ✅ 正确
async def get_document(doc_id: int, user_id: int) -> Document | None:
    ...

# ❌ 错误
async def get_document(doc_id, user_id):
    ...
```

### 3.3 异常处理

```python
# 全局异常通过 core/exceptions.py 统一注册
# 业务层抛出自定义异常，由全局 handler 转换为统一响应

# services 层：
from app.core.exceptions import NotFoundError, PermissionDeniedError

if not document:
    raise NotFoundError(f"文档 {doc_id} 不存在")

# 全局 handler 自动返回：
# {"code": 404, "message": "文档 42 不存在", "data": null}
```

### 3.4 统一响应格式

所有 API 响应必须遵循：

```json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
```

分页响应：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [...],
    "total": 100,
    "page": 1,
    "page_size": 20
  }
}
```

### 3.5 依赖注入模式

```python
# ✅ 通过 FastAPI Depends 注入
@router.get("/me")
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    return UserResponse.model_validate(current_user)

# ❌ 不要在端点内直接创建数据库会话
```

### 3.6 数据库操作

```python
# ✅ 使用 async session
async def get_by_id(db: AsyncSession, user_id: int) -> User | None:
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

# ✅ 批量查询避免 N+1：使用 selectinload / joinedload
stmt = select(KnowledgeBase).options(selectinload(KnowledgeBase.documents))

# ❌ 禁止在循环中 await db.execute
```

---

## 4. 关键模式

### 4.1 Service 层模式

每个 Service 是纯业务逻辑类，**不持有状态**，所有依赖通过构造函数注入：

```python
class RAGService:
    def __init__(
        self,
        embedding: EmbeddingService,
        retriever: RetrieverService,
        reranker: RerankerService,
        generator: GeneratorService,
    ):
        self.embedding = embedding
        self.retriever = retriever
        self.reranker = reranker
        self.generator = generator

    async def query(
        self,
        question: str,
        kb_id: int,
        conversation_history: list[Message] | None = None,
    ) -> RAGResult:
        ...
```

### 4.2 LLM 后端切换

```python
# 通过 .env 的 LLM_BACKEND 配置决定使用哪个后端
# services/llm/base.py 定义抽象基类
# services/llm/openai_backend.py 和 ollama_backend.py 实现

from app.services.llm import get_llm_backend

llm = get_llm_backend()  # 工厂函数，根据配置返回对应实例
response = await llm.chat(messages, stream=True)
```

### 4.3 Embedding 缓存

BGE-M3 模型加载开销大（~2GB），全局单例 + 懒加载：

```python
# db/chroma_store.py 或 services/rag/embedding.py
_embedding_model: SentenceTransformer | None = None

def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(
            settings.EMBEDDING_MODEL,
            device=settings.EMBEDDING_DEVICE,
        )
    return _embedding_model
```

### 4.4 Celery 任务幂等性

所有异步任务必须在数据库状态机驱动下保证幂等：

```
pending → processing → completed / failed
```

任务开始时检查状态，避免重复执行。失败自动重试（指数退避，最多 3 次）。

---

## 5. 常用命令

### 开发环境

> **部署模式**：基础设施（MySQL + Redis + MinIO）通过 Docker 部署在阿里云 ECS
> （公网 IP `118.178.93.114`，root 密码登录），后端代码在本机 Windows 运行并直连云端服务。
> 本机无法运行 Docker Desktop（WSL2 不可用），因此 `docker compose` 命令在服务器上执行（SSH）。

```bash
# 查看云端容器状态
ssh root@118.178.93.114 "docker ps"

# 重启云端基础设施
ssh root@118.178.93.114 "cd /root && docker compose up -d"

# 后端本地启动
uvicorn app.main:app --reload --port 8000

# 启动 Celery worker
celery -A tasks.celery_app worker -l info -c 4

# 数据库迁移
cd backend && alembic upgrade head

# 创建新迁移
cd backend && alembic revision --autogenerate -m "描述"

# 运行测试
cd backend && pytest -v -s --cov=app --cov-report=term-missing

# 下载模型（首次运行前）
python scripts/download_models.py
```

### Docker

```bash
# 查看日志
docker compose -f docker/docker-compose.yml logs -f backend

# 重建镜像
docker compose -f docker/docker-compose.yml build --no-cache backend

# 进入容器
docker exec -it eqa-backend bash

# 清理
docker compose -f docker/docker-compose.yml down -v
```

### API 测试

```bash
# 健康检查
curl http://localhost:8000/health

# Swagger 文档
open http://localhost:8000/api/v1/docs

# ReDoc 文档
open http://localhost:8000/api/v1/redoc
```

---

## 6. 开发工作流

### 每个 Phase 的操作顺序

1. **定义模型** → `models/` → Alembic 迁移
2. **定义 Schema** → `schemas/`（请求/响应的 Pydantic 模型）
3. **实现 Service** → `services/`（纯业务逻辑 + 单元测试）
4. **暴露 API** → `api/v1/`（薄路由层）
5. **注册路由** → `api/v1/__init__.py`（挂载到 FastAPI router）
6. **集成测试** → `tests/`（端到端验证）
7. **Git commit** → 每个 Phase 至少一次提交

### Commit 规范

```
feat(phase1): 初始化项目结构和 Docker 环境
feat(phase2): 实现 JWT 认证和 RBAC 权限
feat(phase3): 实现文档上传和多格式解析
feat(phase4): 实现 RAG 混合检索和流式问答
feat(phase5): 实现 Agent 编排和工具调用
...
fix: 修复文档分块越界问题
refactor: 抽取 RAG pipeline 公共逻辑
docs: 更新 README 部署文档
```

### 代码审查自检

在提交代码前，确认：

- [ ] 所有函数有类型注解
- [ ] API 端点有对应的 Pydantic schema
- [ ] 数据库查询使用了 async session
- [ ] 无 `print()` 残留（使用 `logging`）
- [ ] 无硬编码的配置值（使用 `settings`）
- [ ] 异常使用了自定义异常类
- [ ] 无循环导入
- [ ] 测试通过 `pytest -v`

---

## 7. 注意事项

### 不要做的事

- **不要**在 API 层写业务逻辑——API 只做参数校验 + 调用 service
- **不要**在 models 里写业务方法——models 只定义表结构
- **不要**绕过 services 直接从 api 操作数据库
- **不要**硬编码配置——统一通过 `core/config.py` 的 Settings 读取
- **不要**同步阻塞异步事件循环——Chroma 操作用 `run_in_executor`，CPU 密集型操作用 Celery
- **不要**在未理解现有代码前重构——先问，再改
- **不要**引入未在本方案中列出的新依赖——如需引入，先讨论

### 遇到卡点的处理

1. 先确认是否理解清楚问题
2. 查看相关代码并陈述发现
3. 提出 2-3 种可行方案（含推荐理由）
4. 用户选择后再实现

---

## 8. 文档索引

- [实现步骤](实现步骤.md) — 完整技术方案和 10 个 Phase 的详细计划
- [README](README.md) — 项目介绍和快速开始指南（尚未创建）
