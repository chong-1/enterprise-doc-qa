# Phase 10.1：高并发优化

企业文档智能问答平台扩展功能①：多人同时提问场景的高并发处理。

## 阶段目标

- 答案缓存：热门重复问题零推理、零 LLM API
- Query 向量缓存：同样问题不重复推理 BGE-M3
- Embedding 攒批推理：并发 query 合并为一次批量 encode
- LLM 并发限流：Semaphore 限在途 + 令牌桶限速率 + 429 自动重试
- 缓存失效：文档处理完成 / 删除时清对应 KB 缓存

## 实现文件

| 文件 | 职责 | 类型 |
|---|---|---|
| `app/services/rag/query_cache.py` | 答案缓存 + query 向量缓存（问题规范化 + 哈希键 + KB 级失效，双 async/sync 接口） | 新增 |
| `app/services/llm/rate_limit.py` | 令牌桶限速器（asyncio 版，限速率；与 Semaphore 限在途语义互补） | 新增 |
| `app/services/rag/embedding.py` | 攒批推理：100ms 窗口合并并发 query，后台线程 flush，超时兜底单条推理 | 修改 |
| `app/services/rag/retriever.py` | query 向量化带 Redis 缓存（命中免推理） | 修改 |
| `app/services/rag/pipeline.py` | 问答入口接入答案缓存（含流式模拟输出） | 修改 |
| `app/services/llm/openai_backend.py` | 双层限流（令牌桶 + 信号量）+ 429 重试（Retry-After + 指数退避 + 抖动） | 修改 |
| `app/core/config.py` | 新增 8 个配置项（`QA_CACHE_*` / `LLM_MAX_CONCURRENCY` / `LLM_RATE_*` / `LLM_RETRY_*`） | 修改 |
| `app/api/v1/qa.py` | 响应带 `from_cache` 标识 | 修改 |
| `app/api/v1/documents.py` | 删除文档时清 KB 缓存 | 修改 |
| `app/schemas/qa.py` | `QANonStreamResponse` 增加 `from_cache` 字段 | 修改 |
| `app/tasks/document_tasks.py` | 文档处理完成时清 KB 缓存（最终一致性） | 修改 |

## 验证结果

- 答案缓存命中：20.6s → 2.1s（零 embedding 推理 + 零 LLM 调用）
- 10 并发全部成功；20 并发 19/20（受本机 CPU 推理限制）
- Embedding 8 条并发合并为 1 次批量推理，总耗时降约 5 倍
- 令牌桶 20 请求恰好 2.00s 平滑放行
- 429 限流自动重试恢复（尊重 Retry-After + 指数退避 + 抖动防雪崩）

> **架构约束**：本机 CPU 推理 + 单实例 LLM 配额下实测支撑 ~20-40 同时提问。
> 真正的万级并发需分布式扩展：无状态 API 多 Worker 水平扩展、Embedding 独立 GPU
> 推理服务、多供应商 LLM 配额聚合、Redis 集群、队列削峰与熔断降级。
