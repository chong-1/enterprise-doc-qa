# Phase 5：Agent 智能编排

企业文档智能问答平台第五阶段：基于 LangGraph 的智能 Agent 系统，Router 意图路由 + ReAct 多步推理。

## 阶段目标

- Agent 工具集：search_knowledge_base / list_documents / get_document_info
- Router Agent（LLM 意图分类 → 路由分发）
- ReAct Agent（Thought → Action → Observation 循环，最多 3 轮）
- LangGraph StateGraph 编排（START → router → rag_direct / react_loop → END）
- 对话记忆管理（内存版，Phase 6 迁 Redis）
- Agent API（`agent_mode=true` + 思考链 `thought_chain` 返回）

## 新增文件

| 文件 | 职责 | 类型 |
|---|---|---|
| `backend/app/services/agent/tools.py` | 3 个 Agent 工具：search_kb / list_docs / get_doc_info | 新增 |
| `backend/app/services/agent/graph.py` | LangGraph StateGraph：Router + RAG 直连 + ReAct 循环 | 新增 |
| `backend/app/services/agent/memory.py` | 对话记忆（内存 dict，保留最近 20 条） | 新增 |
| `backend/app/services/agent/__init__.py` | Agent 模块说明 | 修改 |
| `backend/app/api/v1/qa.py` | 新增 `agent_mode` 参数 + 思考链返回 | 修改 |
| `backend/app/schemas/qa.py` | 新增 `thought_chain` 字段 | 修改 |
| `backend/requirements.txt` | 新增 langgraph/langchain/langchain-openai/nest-asyncio | 修改 |

## 核心架构

```
用户提问
    │
    ▼
Router（LLM 意图分类 → JSON {"intent": "simple_qa" | "document_lookup" | "complex"}）
    │
    ├── simple_qa  → RAG 直连（Phase 4 流水线）
    └── document_lookup → ReAct Agent（最多 3 轮）
           │
           └── Thought → Action(tools) → Observation → 循环 → Final Answer
```

### Router
- 用 DeepSeek 做零样本意图分类
- 3 种意图：simple_qa / document_lookup / complex
- 返回 `reasoning` 字段实现白盒可解释

### ReAct Agent
- 标准 Thought → Action → Observation 循环
- 每轮 LLM 自主决定是否需要调工具、调哪个
- kb_id 从 StateGraph state 注入（避免 LLM 幻觉）
- 最多 3 轮，超时强制生成答案

### 思考链
- 每一步记录到 `thought_chain`：[Router 分类 → RAG 检索 / ReAct 工具调用]
- API 返回给前端展示"AI 怎么得出答案的"

## 验证结果

```
场景 1：simple_qa
  问题: "2024年营收目标是多少？"
  意图: [Router] simple_qa
  路径: RAG 直连 → 检索 2 条 → 生成
  答案: "5.2亿元，同比增长35%"

场景 2：document_lookup + ReAct 多步
  问题: "知识库有哪些文档？"
  意图: [Router] document_lookup
  [ReAct 第1轮] list_documents(kb_id=9) → 1 份 PDF
  [ReAct 第2轮] get_document_info(doc_id=11) → 详情
  [ReAct 第3轮] 信息足够，生成答案
  答案: "1 份文档：2024年度经营计划.pdf，PDF，9.76MB，已完成"
```

## 关键设计决策

| 决策 | 选择 | 原因 |
|---|---|---|
| Router 实现方式 | LLM 分类，非训练模型 | 零样本可用，新增意图只需改 prompt |
| ReAct 最大轮数 | 3 轮 | 成本与精度的平衡点 |
| kb_id 注入 | StateGraph state 强制覆盖 | LLM 不知道隐式上下文，会幻觉传值 |
| 工具异步兼容 | nest_asyncio | LangChain @tool 只支持 sync invoke，内部需调 async DB |
| 对话记忆 | 内存 dict | Phase 6 迁 Redis，先跑通流程 |

## 踩坑记录

1. **langchain-openai 漏装**：graph.py 用了 `ChatOpenAI` 但 langchain-openai 未安装
2. **asyncio 嵌套冲突**：FastAPI + LangGraph 均异步，工具需同步但内部调 async DB → `nest_asyncio.apply()`
3. **LLM 工具调用 kb_id 幻觉**：Agent 不知道当前 kb_id，随机编值 → 从 State 强制注入
4. **@tool async 函数 invoke 不可用**：LangChain 1.x 的 async @tool 不支持同步 `invoke()`，必须走 nest_asyncio 桥接

## 新增依赖

```
langgraph            # StateGraph 编排
langchain            # Tool / Message 框架
langchain-community
langchain-openai     # ChatOpenAI（bind_tools 用）
nest-asyncio         # 异步事件循环嵌套
```

## 下一步

Phase 6：对话管理与记忆（Redis 存储 + 长期记忆摘要压缩 + 对话 CRUD API）
