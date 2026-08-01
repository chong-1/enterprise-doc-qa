# Phase 3：文档处理管道

企业文档智能问答平台第三阶段：文件上传 → 多格式解析 → 智能分块 → 异步处理的完整管道。

## 阶段目标

- 文档上传 API（类型/大小校验）+ 本地文件存储
- 多格式解析器：PDF（PyMuPDF）/ Word（python-docx）/ Excel（openpyxl）/ Markdown（markdown-it-py）/ TXT
- 文本清洗（零宽字符/控制字符/空行压缩）
- **BGE-M3 tokenizer 感知的语义分块器**（句子边界 + 512/64 滑动窗口 + 字符偏移溯源）
- Celery 异步任务（状态机 pending → processing → completed/failed，幂等 + 指数退避重试）
- 文档状态查询 / 删除 API + 知识库最小 CRUD（创建/列表/详情）
- **Alembic 正式启用**：基线迁移建齐 6 张业务表

## 实现文件

| 文件 | 职责 | 类型 |
|---|---|---|
| `backend/app/services/document/loader.py` | 本地文件存储（相对路径入 DB，越界防护） | 新增 |
| `backend/app/services/document/parser.py` | 5 格式解析器 + 文本清洗（utf-8/gbk 回退） | 新增 |
| `backend/app/services/document/chunker.py` | BGE-M3 tokenizer 分块：句子贪心 + 超长句硬切 + overlap + 字符偏移 | 新增 |
| `backend/tasks/document_tasks.py` | Celery 任务：状态机驱动、幂等、重试、进程级单例事件循环 | 修改 |
| `backend/app/api/v1/documents.py` | POST /documents/upload、GET /{id}/status、DELETE /{id} | 修改 |
| `backend/app/api/v1/knowledge_bases.py` | 知识库创建/列表/详情（最小实现） | 修改 |
| `backend/alembic/versions/` | 基线迁移 b7b94ea4a7c3：6 张表（kb/documents/conversations/messages/…） | 新增 |
| `backend/app/models/__init__.py` | 聚合导入全部模型（create_all 与 Alembic 一致） | 修改 |
| `backend/app/core/config.py` | HF 镜像配置；Celery broker 改为跟随 REDIS_HOST 动态构造 | 修改 |
| `backend/tasks/celery_app.py` | 改用动态 broker/backend URL | 修改 |
| `backend/tests/test_document_pipeline.py` | 18 例：清洗/解析/分块/存储 | 新增 |

## 核心设计

### 1. 文档入库流程

```
上传 → 类型校验(白名单) + 大小校验(50MB) → 本地存储(uuid 文件名)
     → documents 表(pending) → Celery 派发
     → worker: 解析 → 清洗 → tokenizer 感知分块 → chunk_count + completed
     → 失败: error_message 入库 + 指数退避重试(3 次)
```

### 2. 分块算法（BGE-M3 tokenizer 感知）

```
1. 句子边界切分（中文。！？； + 英文 !?; + 换行）
2. 每句用 XLM-RoBERTa tokenizer（BGE-M3 同源）数 token
3. 贪心累积句子至 chunk_size(默认 512)，相邻 chunk 保留 overlap(64) token 上下文
4. 单句超 chunk_size 时按 token 级硬切（decode 回文本）
5. 每个 chunk 记录 char_start/char_end，供 Phase 4 引用溯源
```

只加载 tokenizer（~20MB），不加载模型权重（Phase 4 才加载 BGE-M3 完整模型）。

### 3. Celery 任务幂等与可靠性

```
pending/processing/failed → 可重入处理；completed → 直接返回（重复派发无害）
失败 → status=failed + 重试 countdown=60×2^retries
进程级单例事件循环贯穿所有任务（见踩坑 4）
```

## 验证结果（curl 全流程 9 项通过）

| 场景 | 结果 |
|---|---|
| 创建知识库 | 200，chunk_size 配置生效 |
| 上传 PDF（3 页中文） | 200 pending → completed，2 chunks |
| 上传 docx / md | 200 → completed |
| 上传 exe | 400 不支持的文件类型 |
| viewer 用户上传 | 403 缺少权限: document:upload（RBAC 生效） |
| 删除文档 | 200 → 再查 404 |
| 重复派发 completed 任务 | 幂等直接返回 |
| Redis broker 断连 | Celery 自动重连，任务不丢 |
| 26 个单元测试 | 全部通过 |

## 踩坑记录（面试素材）

1. **Alembic 双坑**：① alembic.ini 中文注释遇 GBK locale 报 UnicodeDecodeError → 注释改英文；
   ② env.py 骨架用 async engine 却配 pymysql 同步 URL → 改标准同步 engine_from_config
2. **LONGTEXT 导入**：`from sqlalchemy import LONGTEXT` 不存在，需 `sqlalchemy.dialects.mysql`（Phase 1 骨架遗留，从未被导入所以没暴露）
3. **relationship 赋值触发 lazy load**：`kb.documents = []` 补 document_count 时，SQLAlchemy setter 先读取旧值 → async 下 MissingGreenlet。新建记录文档数必为 0，直接构造响应
4. **asyncio.run 与连接池冲突**：每个任务新 loop 并关闭，aiomysql 连接池跨任务复用旧 loop 的连接 → `AttributeError: 'NoneType' has no attribute 'send'`。改为**进程级单例事件循环**（run_until_complete）
5. **celery prefork 在 Windows 崩溃**：celery 5.4 + Windows + Python 3.12 下 fast_trace_task `ValueError: not enough values to unpack` → 开发用 `-P solo`
6. **Redis broker 跨公网断连**：长连接被中间设备掐断（同 Phase 2 MySQL 问题）→ Celery 自动重连，任务积压不丢
7. **HF 直连被墙**：huggingface.co SSL 证书校验失败 → `HF_ENDPOINT=https://hf-mirror.com`（config 可配）
8. **Windows curl 中文 JSON**：Git Bash GBK 终端发中文 body → 解析失败，用 `-d @file.json`（UTF-8 文件）
9. **gitignore 嵌套坑**：`data/uploads/*` 不匹配深层文件 → 改为 `data/uploads/`

## 如何运行

```bash
# 前提：云端 MySQL + Redis 已启动，eqa 环境已装 Phase 3 依赖
cd backend
/c/Users/86150/anaconda3/envs/eqa/python.exe -m uvicorn app.main:app --port 8000
# 新终端：
/c/Users/86150/anaconda3/envs/eqa/python.exe -m celery -A tasks.celery_app worker -l info -P solo
```

```bash
# 登录 → 建库 → 上传 → 查状态
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123456"}' | python -c "import sys,json;print(json.load(sys.stdin)['data']['access_token'])")
curl -X POST http://localhost:8000/api/v1/knowledge-bases -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"name":"demo-kb"}'
curl -X POST http://localhost:8000/api/v1/documents/upload -H "Authorization: Bearer $TOKEN" \
  -F "kb_id=1" -F "file=@test.pdf"
curl http://localhost:8000/api/v1/documents/1/status -H "Authorization: Bearer $TOKEN"
# → {"status":"completed","chunk_count":N}
```

## 里程碑

- 本地提交 `002a0af` phase3：文档处理管道

下一步：**Phase 4 RAG 核心引擎**（BGE-M3 完整模型 + Chroma 向量库 + 混合检索 + Reranker + LLM 生成，需安装 torch 等重依赖约 3GB）
