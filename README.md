# 企业文档智能问答平台 (Enterprise QA Platform)

基于 **RAG + Multi-Agent** 架构的企业级文档智能问答系统，支持多格式文档解析、混合检索、Agent 智能编排、多轮对话记忆与 RBAC 权限管理。

## ✨ 核心特性

- 📄 **多格式文档解析**：PDF / Word / Excel / Markdown / TXT，自动提取文本并智能分块
- 🔍 **混合检索 RAG**：BGE-M3 稠密向量 + BM25 稀疏词汇双路检索，RRF 融合排序
- 🤖 **Agent 编排**：基于 LangGraph 的 Router + ReAct 智能体，支持工具调用和多步推理
- 💬 **流式对话**：SSE 流式输出 + 引用溯源 + 多轮上下文记忆 + LLM 摘要压缩
- 🔐 **企业级安全**：JWT 认证 + RBAC 权限 + 知识库级角色隔离（owner/editor/viewer）+ 操作审计日志 + **提示注入防御**（五层防护）
- ⚡ **异步架构**：FastAPI 全异步 + Celery 任务队列 + Redis 缓存/限流/对话记忆
- 🎨 **现代化前端**：Vue 3 + Element Plus，7 个页面，SSE 流式聊天

## 🛠 技术栈

| 层 | 技术 |
|---|---|
| 后端框架 | Python 3.12 + FastAPI + Pydantic v2 |
| 数据库 | MySQL 8.0 + SQLAlchemy 2.0 (async) + Alembic |
| 向量数据库 | Chroma (PersistentClient, 本地持久化) |
| Embedding | BGE-M3（稠密 1024d + 稀疏词汇权重） |
| LLM | DeepSeek API (OpenAI 兼容接口) |
| 异步任务 | Celery + Redis (Broker) |
| Agent 框架 | LangGraph 1.x |
| 前端 | Vue 3 + Vite + Element Plus 2.9 + Pinia + Vue Router |
| 部署 | Docker Compose (MySQL/Redis/MinIO) |

## 🏗 系统架构

```
┌──────────────────────────────────────────────────────┐
│             前端 (Vue 3 + Element Plus)                │
│   登录/仪表盘/知识库/文档/问答/用户管理/审计日志         │
├──────────────────────────────────────────────────────┤
│                  FastAPI 后端 (8000)                    │
│  ┌──────┬────────┬────────┬────────────┬────────┐    │
│  │ 认证  │ 文档管理│ RAG问答 │ Agent编排  │ 企业特性│    │
│  │ JWT  │ 解析分块│ 混合检索 │ Router+ReAct│审计/限流│   │
│  └──────┴────────┴────────┴────────────┴────────┘    │
├──────────────────────────────────────────────────────┤
│   Redis(6379) │ Celery Worker │ 本地文件存储           │
├──────────────────────────────────────────────────────┤
│   MySQL(3306) │  Chroma(本地) │ BGE-M3 Embedding      │
└──────────────────────────────────────────────────────┘
```

## 📦 项目结构

```
├── backend/
│   ├── app/
│   │   ├── api/v1/          # 路由层（auth/kb/documents/qa/conversations/users/audit_logs/system_configs）
│   │   ├── core/            # 配置/安全/依赖注入/异常
│   │   ├── models/          # SQLAlchemy ORM（user/kb/document/conversation/audit_log/system_config）
│   │   ├── schemas/         # Pydantic 请求/响应
│   │   ├── services/        # 业务逻辑（document/rag/agent/llm/audit/conversation/system_config）
│   │   ├── db/              # MySQL session / Chroma / Redis 封装
│   │   └── middleware/      # CORS / 限流
│   ├── tasks/               # Celery 异步任务（文档解析→分块→Embedding→Chroma 写入）
│   ├── tests/               # pytest（单元测试 + API 集成测试）
│   ├── scripts/             # 管理员创建 / RAG 评估 / 验证脚本
│   └── alembic/             # 数据库迁移
├── frontend/                # Vue 3 前端
│   └── src/
│       ├── api/             # axios 封装
│       ├── router/          # 路由 + 导航守卫
│       ├── stores/          # Pinia 状态管理
│       └── views/           # 7 个页面
├── docker/                  # Docker Compose
└── 实现步骤.md               # 完整技术方案与 10 个 Phase 计划
```

## 🚀 快速开始

### 前提条件

- Python 3.12 + conda 环境 `eqa`
- Node.js 20+ (前端)
- MySQL 8.0 + Redis (云端 Docker 或本地)
- BGE-M3 模型 (~2.5GB, 下载到 D:/huggingface)

### 1. 启动基础设施

```bash
# 云端 Docker（阿里云 ECS）
ssh root@120.27.140.97 "cd /root && docker compose up -d"

# 或本地 Redis（Windows）
D:\redis\redis-server.exe
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env: MYSQL_HOST / REDIS_HOST / LLM_API_KEY 等
```

### 3. 安装依赖

```bash
conda activate eqa
cd backend
pip install -r requirements.txt

# 前端
cd ../frontend
npm config set registry https://registry.npmmirror.com
npm install
```

### 4. 数据库初始化

```bash
cd backend
alembic upgrade head           # 应用所有迁移
python scripts/create_admin.py  # 创建管理员
```

### 5. 启动服务

```bash
# 终端 1: 后端 API
cd backend && uvicorn app.main:app --reload --port 8000

# 终端 2: Celery Worker（Windows 必须 -P solo）
cd backend && celery -A tasks.celery_app worker -l info -P solo

# 终端 3: 前端
cd frontend && npx vite --host 0.0.0.0 --port 5173
```

### 6. 访问

| 地址 | 说明 |
|------|------|
| http://localhost:5173 | 前端界面 |
| http://localhost:8000/health | 健康检查 |
| http://localhost:8000/api/v1/docs | Swagger API 文档 |
| http://localhost:8000/api/v1/redoc | ReDoc 文档 |

## 🔑 默认账号

| 角色 | 账号 | 密码 |
|------|------|------|
| 管理员 | admin | Admin123456 |
| 普通用户 | mytest | test123456 |

## 🧪 测试

```bash
# 单元测试 + 文档流水线 + 注入防御红队测试
cd backend && pytest tests/test_security.py tests/test_document_pipeline.py tests/test_injection_defense.py -v

# API 集成测试（需要后端运行中）
cd backend && pytest tests/test_api_integration.py -v -p no:asyncio

# RAG 评估
cd backend && python scripts/eval_rag.py --kb-id 9

# Phase 7 功能验证
cd backend && python scripts/verify_phase7.py
```

> 集成测试结果：32/32 通过，覆盖认证/知识库/文档/问答/对话/用户管理/审计/配置 8 个模块。

## 📅 开发进度

| Phase | 内容 | 状态 |
|-------|------|------|
| 1 | 项目骨架 + Docker 环境 | ✅ |
| 2 | JWT 认证 + RBAC 权限 | ✅ |
| 3 | 文档上传 + 多格式解析 + 智能分块 | ✅ |
| 4 | RAG 混合检索 + 流式问答 | ✅ |
| 5 | Agent 智能编排 (Router + ReAct) | ✅ |
| 6 | 对话管理与两层记忆 | ✅ |
| 7 | 企业特性（多KB隔离/成员管理/审计/软删除/配置/限流） | ✅ |
| 8 | 前端界面（Vue3 + ElementPlus，7 页面） | ✅ |
| 9 | 测试与优化 | ✅ |
| 10.1 | 高并发优化（多级缓存 / Embedding 攒批 / LLM 限流与重试） | ✅ |
| 10.2 | 提示词注入防御（五层防御 / 审计回溯 / 红队测试） | ✅ |

## ⚡ 高并发优化（Phase 10.1）

针对多人同时提问场景的 8 项优化：

| 优化项 | 设计要点 | 效果 |
|---|---|---|
| 答案缓存 | 问题规范化（去标点/全半角/小写）+ 哈希键 `qa:ans:{kb_id}:{hash}`，KB 级失效 | 缓存命中 20.6s → 2.1s |
| Query 向量缓存 | 同样问题不重复推理 BGE-M3，复用 dense 向量 | 检索阶段免推理 |
| Embedding 攒批推理 | 100ms 窗口合并并发 query 为一次批量 encode，后台线程异步 flush | 并发冷查询总耗时降约 5 倍 |
| LLM 并发限流 | asyncio.Semaphore(5) 限制同时在途请求 | 防长请求堆积 |
| 令牌桶限速 | 5 req/s + 突发 10，主动低于 API 配额 | 20 并发请求 2.00s 平滑放行 |
| 429 自动重试 | 尊重 `Retry-After` 头 + 指数退避 + 随机抖动 | 限流后自动恢复，防重试雪崩 |
| 缓存失效 | 文档处理完成 / 删除时清对应 KB 缓存 | 答案跟随文档更新（最终一致） |
| 全部配置化 | 8 个配置项（`QA_CACHE_*` / `LLM_MAX_CONCURRENCY` / `LLM_RATE_*` 等） | 改 `.env` 即可调优 |

实测验证：缓存命中 20.6s → 2.1s；10 并发全部成功，20 并发 19/20；embedding 8 条并发合并为 1 次推理；令牌桶 20 请求恰好 2.00s。

> **架构约束**：本机 CPU 推理 + 单实例 LLM 配额下实测支撑 ~20-40 同时提问。真正的万级并发需分布式扩展：无状态 API 多 Worker 水平扩展、Embedding 独立 GPU 推理服务、多供应商 LLM 配额聚合、Redis 集群、队列削峰与熔断降级。

## 🛡 提示词注入防御（Phase 10.2）

针对 RAG 场景（用户上传文档 → 检索 → 拼进提示词）的**间接提示注入**攻击（OWASP LLM Top 10，重点 LLM01 提示注入 / LLM07 系统提示词泄露），实施五层附加式防御：

| 防御层 | 位置 | 设计 |
|---|---|---|
| 上传扫描 | 文档解析后 | 扫描全文注入特征（强特征长短语，低误报），命中记日志不阻断 |
| 检索过滤 | RAG 流水线 | 含注入特征的 chunk 剔除，不进 prompt（**最关键拦截点**） |
| Spotlighting | 提示词构建 | `<user_data>` 边界标记 + 信任声明（标记内内容一律视为数据，不得作为指令执行） |
| 输出校验 | 生成后 | 密钥 / 系统提示词泄露扫描 |
| 审计回溯 | 每次问答 | `qa:retrieval` 记录检索片段 + 剔除结果，事后可还原攻击 |

**实现文件**：`services/injection_guard.py`（5 类强特征注入模式 + base64/hex 编码绕过解码检测）、`rag/generator.py`（Spotlighting 标记 + 信任声明）、`rag/pipeline.py`（检索过滤 + 问答审计 + 输出校验）、`agent/tools.py`（工具返回值同等级标记）、`tasks/document_tasks.py`（上传环节扫描）。

**验证结果**：红队测试集 15/15 通过（攻击识别 / 编码绕过 / 误报控制 / 检索过滤 / 边界标记 / 输出校验），现有测试无回归。

> **设计原则**：全部附加式实现（不改变原有逻辑/功能/框架）；防御为 fail-open 设计（检测失败不阻断主流程）；关键词防线可被语义级攻击绕过，强防御依赖标记 + 模型信任声明。

## 📚 文档

- [实现步骤.md](实现步骤.md) — 完整技术方案、数据库设计、分阶段实施计划
- [CLAUDE.md](CLAUDE.md) — 项目开发规范（架构边界/编码约定/工作流）

