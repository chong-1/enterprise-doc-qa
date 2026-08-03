# Phase 4：RAG 核心引擎

企业文档智能问答平台第四阶段：端到端 RAG 问答——从文档向量化到检索增强生成的完整流水线。

## 阶段目标

- BGE-M3 Embedding（dense 1024d + sparse 词汇权重，一次调用同时产出）
- Chroma 向量存储（chunk 写入 + Dense 语义检索）
- 混合检索（Dense + Sparse BM25 → RRF 融合）
- BGE-Reranker-v2-m3 精排（已实现，开发环境内存限制暂未启用）
- LLM 抽象层（OpenAI/DeepSeek 兼容，流式 + 非流式）
- QA API（非流式 / SSE 流式 + 引用溯源）
- 文档处理流程延长：分块 → Embedding → Chroma 入库

## 实现文件

| 文件 | 职责 | 类型 |
|---|---|---|
| `backend/app/services/rag/embedding.py` | BGE-M3 懒加载单例，encode() 一次产出 dense+sparse | 新增 |
| `backend/app/services/rag/retriever.py` | Dense(Chroma) + Sparse(纯Python BM25) → RRF 融合 | 新增 |
| `backend/app/services/rag/reranker.py` | BGE-Reranker-v2-m3 精排（因内存跳过） | 新增 |
| `backend/app/services/rag/generator.py` | System Prompt + 上下文拼装 + token 预算 + LLM 调用 | 新增 |
| `backend/app/services/rag/pipeline.py` | RAGPipeline：检索→排序→生成→引用 | 新增 |
| `backend/app/services/llm/base.py` | LLM 抽象基类（chat / chat_stream） | 新增 |
| `backend/app/services/llm/openai_backend.py` | OpenAI/DeepSeek 兼容后端 | 新增 |
| `backend/app/services/llm/__init__.py` | LLM 后端工厂 `get_llm_backend()` | 修改 |
| `backend/app/db/chroma_store.py` | 扩展 `add_chunks()` 写入 + `search_dense()` 检索 | 修改 |
| `backend/app/api/v1/qa.py` | POST /qa/{kb_id} 非流式 + SSE 流式问答 | 修改 |
| `backend/app/schemas/qa.py` | QARequest / QANonStreamResponse / SourceCitation | 修改 |
| `backend/app/core/config.py` | HF_HOME / HF_ENDPOINT / Celery broker 动态 URL | 修改 |
| `backend/tasks/document_tasks.py` | 流程延长：分块→embedding→Chroma入库→completed | 修改 |
| `backend/tasks/celery_app.py` | 改用 settings 动态 broker URL | 修改 |
| `backend/app/services/document/chunker.py` | 新增 HF_HOME env 设置（分块+生成都用） | 修改 |
| `backend/requirements.txt` | 新增 torch/transformers/sentencepiece（Phase 3 补充） | 修改 |
| `backend/start_celery.py` | Celery Worker 启动脚本（Windows 兼容） | 新增 |

## 核心架构

```
用户提问
    │
    ▼
① BGE-M3 向量化问题 → 1024d dense vector
    │
    ├──→ ②a Chroma Dense 检索 (top_k=20)
    │        余弦相似度搜最接近的 chunk
    │
    └──→ ②b BM25 Sparse 检索 (top_k=20)
             关键词精确匹配
    │
    ▼
③ RRF 融合排序
    score = 1/(60+rank_dense) + 1/(60+rank_sparse)
    │
    ▼
④ 上下文拼装 + token 预算控制
    System Prompt + [资料1] 来源 + 文本片段
    │
    ▼
⑤ DeepSeek API 生成答案 (SSE 流式)
    │
    ▼
⑥ 返回：答案 + 引用溯源（文档名 + 原文片段 + 得分）
```

## 关键技术选型

### BGE-M3
- 单一模型同时产出 dense(1024d) + sparse 双路向量
- 中英双语，中文 MTEB 榜单 SOTA
- CPU 可运行，模型加载约 2.5GB 内存
- 首次下载 ~8.6GB → D:/huggingface（hf-mirror.com 镜像）

### 混合检索
- Dense（语义匹配） + Sparse（关键词匹配），互补
- RRF 融合不需分数校准，不同量纲直接调和使用
- 纯 Python BM25 实现，零额外依赖

### 生成管道
- System Prompt 约束只根据文档回答
- Token 预算控制（复用 BGE-M3 tokenizer 精确数 token）
- DeepSeek API（OpenAI 兼容协议），支持流式 SSE

## 踩坑记录

1. **BGE-M3 下载卡 99%**：hf-mirror.com 拦截仓库里 `.DS_Store` 文件 → 手动删孤儿 .incomplete + 创建 dummy 文件
2. **FastAPI Segfault**：BGE-M3(2.5G) + Reranker(2.2G) 同时加载 > 本机空闲内存 → 跳过 Reranker，RRF 分直排 top-5
3. **Celery Worker 卡 PROCESSING**：FastAPI 持有的模型占满内存，Worker 加载第二份 OpenBLAS 报错 → 文档处理与问答分步执行，不同时跑
4. **Redis 跨公网断连**：模型下载 30 分钟阻塞导致连接被掐 → Phase 6 考虑本机 Redis
5. **RRF 分 ≈0.03 不代表质量差**：这是排名调和值，不是相似度。真正相关度分需要 Reranker
6. **Git Bash 中文 JSON 解析失败**：GBK 编码问题，中文测试用 Swagger

## 验证结果

```
上传 PDF → 2 chunks → BGE-M3 向量化 → Chroma 入库
问题: "What is the 2024 revenue target?"
答案: "2024年公司整体营收目标为人民币5.2亿元，同比增长35%。"
引用: 2 条（来源 2024年度经营计划.pdf，含原文片段）
耗时: 14,234ms
```

## 下一步

Phase 5：Agent 智能编排（LangGraph + Router/ReAct Agent + 工具调用）
