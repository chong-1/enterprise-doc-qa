# 企业文档智能问答平台 (Enterprise QA Platform)

基于 **RAG + Multi-Agent** 架构的企业级文档智能问答系统，支持多格式文档解析、混合检索、Agent 智能编排、多轮对话记忆与 RBAC 权限管理。适用于企业内部知识库问答、规章制度查询、文档辅助分析等场景。

## ✨ 核心特性

- 📄 **多格式文档解析**：PDF / Word / Excel / Markdown / TXT，自动提取文本并智能分块
- 🔍 **混合检索 RAG**：BGE-M3 稠密向量 + 稀疏词汇双路检索，RRF 融合排序，BGE-Reranker-v2 精排
- 🤖 **Multi-Agent 编排**：基于 LangGraph 实现 Router / ReAct / Summary / SQL 多 Agent 状态图，支持复杂多步推理与工具调用
- 💬 **流式对话**：SSE 流式输出 + 引用溯源（来源文档、原文片段、页码），多轮上下文记忆
- 🔐 **企业级安全**：JWT 认证 + RBAC 三级权限（角色-知识库-文档），操作审计日志
- ⚡ **异步架构**：FastAPI 全异步 + Celery 任务队列解耦，Redis 缓存与对话记忆
- 🚀 **灵活部署**：基础设施 Docker 化，LLM 双后端（OpenAI 兼容 / Ollama 本地）可切换

## 🛠 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.12 + FastAPI + Pydantic v2 |
| 数据库 | MySQL 8.0 + SQLAlchemy 2.0 (async) + Alembic |
| 向量库 | Chroma (PersistentClient, 本地持久化) |
| Embedding | BGE-M3（稠密 1024d + 稀疏词汇权重） |
| Reranker | BGE-Reranker-v2-m3 |
| LLM | OpenAI 兼容接口 / Ollama 本地，双后端可切换 |
| 异步任务 | Celery + Redis |
| Agent | LangGraph |
| OCR | PaddleOCR |
| 对象存储 | MinIO（开发期可选本地文件系统） |
| 容器化 | Docker Compose |

## 🏗 系统架构

```
┌──────────────────────────────────────────────────────┐
│            前端 (Vue 3 + Element Plus)                 │
├──────────────────────────────────────────────────────┤
│                   FastAPI 后端                         │
│  ┌───────┬────────┬────────┬────────────┐            │
│  │ 认证   │ 文档管理 │ RAG问答 │ Agent编排   │            │
│  │ JWT   │ 解析/分块│ 混合检索 │ LangGraph   │            │
│  └───────┴────────┴────────┴────────────┘            │
├──────────────────────────────────────────────────────┤
│        Redis  │  Celery  │  MinIO(可选)               │
├──────────────────────────────────────────────────────┤
│        MySQL  │  Chroma  │  本地文件系统               │
├──────────────────────────────────────────────────────┤
│   BGE-M3 Embedding │ BGE-Reranker │ LLM (API/Ollama)  │
└──────────────────────────────────────────────────────┘
```

**RAG 检索流水线**：

```
用户提问 → 混合检索(稠密+稀疏) → RRF 融合 → Reranker 精排 → 上下文组装 → LLM 生成 → 引用溯源
```

## 📦 项目结构

```
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/          # 路由层（薄）
│   │   ├── core/            # 配置/安全/依赖注入/异常
│   │   ├── models/          # SQLAlchemy ORM 模型
│   │   ├── schemas/         # Pydantic 请求/响应模型
│   │   ├── services/        # 业务逻辑层
│   │   │   ├── document/    # 文档解析/分块
│   │   │   ├── rag/         # Embedding/检索/重排/生成
│   │   │   ├── agent/       # Agent 编排
│   │   │   └── llm/         # LLM 双后端封装
│   │   ├── db/              # MySQL/Chroma/Redis 封装
│   │   └── middleware/      # CORS/日志/限流
│   ├── tasks/               # Celery 异步任务
│   ├── tests/               # pytest 测试
│   └── alembic/             # 数据库迁移
├── docker/                  # Docker Compose 配置
├── scripts/                 # 初始化/种子/模型下载脚本
├── frontend/                # Vue 3 前端（可选）
├── 实现步骤.md              # 完整技术方案与 10 个 Phase 计划
└── CLAUDE.md                # 项目开发规范
```

## 🚀 快速开始

### 1. 启动基础设施（MySQL + Redis + MinIO）

```bash
docker compose -f docker/docker-compose.yml up -d
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填写数据库连接、LLM API Key 等
```

### 3. 安装后端依赖并初始化

```bash
conda create -n eqa python=3.11 -y
conda activate eqa
cd backend && pip install -r requirements.txt

# 初始化数据库（建表 + 默认角色/权限 + admin 账号）
cd .. && python scripts/init_db.py

# 预下载 Embedding / Reranker 模型（首次运行，约 3GB）
python scripts/download_models.py
```

### 4. 启动后端

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### 5. 访问

| 地址 | 说明 |
|------|------|
| http://localhost:8000/health | 健康检查 |
| http://localhost:8000/api/v1/docs | Swagger 接口文档 |
| http://localhost:8000/api/v1/redoc | ReDoc 文档 |

### 常用命令

```bash
# 数据库迁移
cd backend && alembic upgrade head

# 运行测试
cd backend && pytest -v --cov=app --cov-report=term-missing

# 启动 Celery worker
celery -A tasks.celery_app worker -l info -c 4
```

## 🔑 默认账号

| 角色 | 账号 | 密码 |
|------|------|------|
| 管理员 | admin | admin123456 |

> ⚠️ 生产环境请务必修改默认密码。

## 📅 开发计划（10 个 Phase）

| Phase | 内容 | 状态 |
|-------|------|------|
| 1 | 项目骨架 + Docker 环境 + 认证基础 | ✅ 完成 |
| 2 | JWT 认证 + RBAC 权限 | ⏳ 进行中 |
| 3 | 文档上传 + 多格式解析 + 智能分块 | 待开始 |
| 4 | RAG 混合检索 + 流式问答（核心） | 待开始 |
| 5 | Agent 智能编排 | 待开始 |
| 6 | 对话管理与记忆 | 待开始 |
| 7 | 企业特性（审计/多知识库/限流） | 待开始 |
| 8 | 前端界面 | 待开始 |
| 9 | 测试与性能优化 | 待开始 |
| 10 | 扩展加分项 | 待开始 |

## 📚 文档

- [实现步骤.md](实现步骤.md) — 完整技术方案、数据库设计、分阶段实施计划
- [CLAUDE.md](CLAUDE.md) — 项目开发规范（架构边界/编码约定/工作流）

## 📄 License

MIT
