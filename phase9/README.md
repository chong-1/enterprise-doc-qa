# Phase 9：测试与前端优化

企业文档智能问答平台第九阶段：API 集成测试 + RAG 评估 + 前端 UI 重构。

## 阶段目标

- API 集成测试全覆盖（8 模块 32 用例）
- RAG 检索质量评估脚本（Recall@5 / MRR / Faithfulness）
- 前端 UI 大幅优化（QA 聊天重构 + 全局视觉升级）
- README 更新为当前项目状态

## 新增/修改文件

### 新增

| 文件 | 职责 |
|---|---|
| `tests/test_api_integration.py` | API 集成测试（32 项，httpx + pytest） |
| `scripts/eval_rag.py` | RAG 评估脚本（检索质量 + 忠实度） |

### 修改

| 文件 | 变更 |
|---|---|
| `frontend/src/views/QAChat.vue` | 全面重构：头像气泡/流式光标/引用折叠卡片/复制按钮/Enter 发送/智能滚动/空态引导；按 content-type 分流 Agent JSON / SSE |
| `frontend/src/views/Layout.vue` | 深色侧边栏/面包屑/用户状态底栏/管理员菜单分组 |
| `frontend/src/views/Dashboard.vue` | 骨架屏加载/统计卡片重设计/知识库快捷列表/操作动态流；修复统计快照 bug |
| `backend/services/agent/graph.py` | Agent 图：取最后一条用户消息/检索与生成携带对话历史（指代消解） |
| `backend/services/rag/retriever.py` | 检索结果补 `dense_score` 真实余弦相似度 |
| `backend/services/rag/generator.py` | 引用优先展示 `dense_score`（RRF 分不适合当百分比） |
| `backend/services/conversation_service.py` | 修复 `get_context` 顺序反转（rpush 追加后 lrange 已是正序） |
| `backend/services/llm/openai_backend.py` | 清理 conda 注入的无效 `SSL_CERT_FILE`（LLM 500 根因） |
| `README.md` | 更新为当前状态：开发进度/前端启动/测试命令/默认账号 |

## 测试结果

```
API 集成测试：32 passed in 24.02s

TestAuth           : 5/5 ✅  (登录/错误密码/重复注册/me端点/refresh)
TestKnowledgeBases : 6/6 ✅  (创建/列表/详情/更新/隔离/成员管理)
TestDocuments      : 4/4 ✅  (上传/列表/状态/软删除)
TestQA             : 3/3 ✅  (非流式/权限403/Agent模式)
TestConversations  : 3/3 ✅  (列表/详情/消息)
TestUserManagement : 4/4 ✅  (列表/搜索/越权403/更新用户)
TestAuditLogs      : 3/3 ✅  (列表/按操作筛选/越权403)
TestSystemConfig   : 3/3 ✅  (列表/更新回读/非法键被拒)
TestCleanup        : 1/1 ✅  (删除KB级联)
```

## Bug 修复记录（4 个前后端联动 bug + 2 个独立 bug）

| # | Bug | 根因 | 修复 |
|---|-----|------|------|
| 1 | Agent 模式前端空气泡（刷新后才显示） | 前端一律按 SSE 解析，但 Agent 模式后端返回普通 JSON（success_response） | 前端按 `content-type` 分流：SSE 走流式解析，否则 JSON 解析并取 answer/citations/conversation_id |
| 2 | 检索相似度只有 3% | `hybrid_search` 的 score 是 RRF 融合分（1/(k+rank)，量级 0.01-0.03），被前端当相似度百分比 | 检索结果补 `dense_score`（真实余弦相似度 0.7-0.9），`format_citations` 优先用它 |
| 3 | RAG 模式两条一模一样的回复 | SSE `done` 事件携带完整答案，前端把 done 的 data 也当 token 追加 → 内容重复两遍 | 前端跟踪 `currentEvent`，`event: done` 后的 data 行跳过 |
| 4 | Agent 短期记忆失效（"它"指代失败） | 三层：① `get_context` 用 `reversed` 反转了正序历史 ② rag_direct 生成时不带对话历史 ③ 检索 query 是裸指代词，检索跑偏到 LLM-Agent 内容 | ① 去掉 reversed ② 生成 prompt 携带最近历史 ③ 检索 query 拼接最近 300 字对话历史做指代消解；react 最终生成也把历史轮次放前面 |
| 5 | 仪表盘统计全 0 | `statCards` 数组创建时快照了 `stats.kbCount` 的初始值 0，模板 `card.value` 永远显示 0 | 改为 `stats[card.key]` 动态读取响应式值 |
| 6 | 问答接口 500 | `conda activate` 注入 `SSL_CERT_FILE` 指向不存在的 `<env>/ssl/cacert.pem`，httpx 初始化崩溃 | 创建 AsyncOpenAI 前校验文件存在性，无效则删除该环境变量（回退 certifi 证书） |

## 注意

- uvicorn `--reload` 的 WatchFiles 会漏检文件修改（改多个文件可能只 reload 一次），改后端代码后若日志无 `Reloading...` 需手动重启。
- Windows 下 `conda activate eqa` 注入的 `SSL_CERT_FILE` 路径无效，代码已防御；脚本直接跑 httpx 时若报 FileNotFoundError，先 `unset SSL_CERT_FILE`。

## 前端优化要点

### QA 聊天页
- 用户气泡蓝色右侧 + 头像首字母，助手气泡白色左侧 + 🤖 头像
- 流式输出闪烁光标动画（`▊` + CSS blink）
- 引用改为可折叠卡片，含文档名 + 相关度进度条 + 原文片段
- 每条助手消息带复制按钮
- Enter 发送 / Shift+Enter 换行
- 智能滚动：用户上翻时不自动滚底，新消息或点发送才滚
- 空态引导：三项核心功能介绍

### 全局 UI
- 侧边栏：深色背景 `#1d1e2c`，菜单项圆角 + active 渐变高亮
- 面包屑导航
- Dashboard：骨架屏加载态、统计卡片 hover 阴影、非管理员快捷入口
- 统一配色：`#409EFF` 主题蓝 / `#f5f7fa` 背景灰

## Git 上传

```bash
cd /d/process
git add phase9/
git commit -m "phase9：测试与前端优化"
git push origin main
```

## 下一步

Phase 10：扩展加分项（知识图谱/CI-CD/监控面板等，按需选做）
