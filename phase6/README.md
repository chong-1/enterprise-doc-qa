# Phase 6：对话管理与记忆

企业文档智能问答平台第六阶段：完整的对话管理系统 + 短期/长期记忆架构。

## 阶段目标

- 对话 CRUD API（自动创建 / 列表 / 详情 / 删除）
- LLM 自动生成对话标题（根据首条消息）
- 消息列表 API（分页 + 引用溯源）
- 短期记忆：Redis 存储最近 10 轮对话上下文
- 长期记忆：超 10 轮自动 LLM 摘要压缩 → Redis 头部注入
- 本机 Redis 部署（替代云端跨公网不可靠方案）

## 新增/修改文件

| 文件 | 职责 | 类型 |
|---|---|---|
| `backend/app/services/conversation_service.py` | CRUD + 消息存储 + 标题生成 + Redis 记忆 + 摘要压缩 | 新增 |
| `backend/app/api/v1/conversations.py` | 对话列表/详情/删除 + 消息分页 API | 修改 |
| `backend/app/api/v1/qa.py` | 集成对话创建/消息存储/Redis 记忆；响应补 conversation_id | 修改 |
| `backend/app/schemas/qa.py` | QA 响应补 conversation_id 字段 | 修改 |
| `backend/.env` | REDIS_HOST=localhost | 修改 |

## 核心架构

```
用户提问（不传 conversation_id）
    │
    ▼
自动创建对话 → LLM 生成标题 → 存储 MySQL
    │
存储消息到 MySQL（user + assistant + citations）
    │
写入 Redis（conv_memory:{id} → [user_msg, assistant_msg, ...]）
    │
超过 10 轮时 → LLM 压缩老消息为摘要 → 插入 Redis 头部
    │
返回答案 + conversation_id
```

### 两层记忆

```
短期记忆（Redis List）
  ├── 最近 10 对消息（20 条）
  ├── 每次问答追加到队尾
  └── Agent 问答时从队头加载拼到 prompt

长期记忆（摘要压缩）
  ├── 超出 10 轮时触发
  ├── 老消息用 DeepSeek 压缩为 ≤200 字摘要
  └── 以 [历史摘要] 形式插入队列头部
```

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /conversations | 对话列表（分页） |
| GET | /conversations/{id} | 对话详情 |
| DELETE | /conversations/{id} | 删除（级联消息+引用+Redis） |
| GET | /conversations/{id}/messages | 消息列表（分页+引用） |
| POST | /qa/{kb_id} | 问答（自动创建对话，返回 conversation_id） |

## 验证结果

```
首轮: POST /qa/9 {"question":"What is the 2024 revenue target?"}
  → conversation_id=4, 标题 "What is the 2024 revenue target..."

追问: POST /qa/9 {"question":"What is the growth rate?","conversation_id":4}
  → "同比增长35%"（基于历史上下文）

消息: GET /conversations/4/messages → 4 条消息，含引用

列表: GET /conversations → ID=4, 标题已生成, 消息数 4
```

## 踩坑

1. **标题生成超时**：DeepSeek API 偶发延迟 → `asyncio.wait_for(10s)` + 截断 fallback
2. **conversation_id 未返回**：QA 响应无 conv_id，用户无法追问 → schema 补 conversation_id 字段

## 下一步

Phase 7：企业特性（多知识库隔离、权限细化、审计日志、限流）
