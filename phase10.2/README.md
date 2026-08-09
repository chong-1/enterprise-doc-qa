# Phase 10.2：提示词注入防御

企业文档智能问答平台扩展功能②：针对 RAG 场景（用户上传文档 → 检索 → 拼进提示词）的提示注入攻防。

> 背景：平台解析用户上传文档，检索结果直接拼进提示词——典型的**间接提示注入**高危场景。
> 攻击者上传一个含恶意指令的文档即可尝试劫持 LLM。本阶段按 OWASP LLM Top 10
> （重点 LLM01 提示注入 / LLM07 系统提示词泄露）实施五层防御。

## 阶段目标（RAG 场景五项要点）

1. **上传环节**：扫描文档注入特征，命中记日志（附加式，不阻断解析）
2. **检索环节**：检索结果合法性过滤——含注入特征的 chunk 剔除，不进 prompt
3. **生成环节**：Spotlighting 边界标记 + 信任声明 + 输出侧密钥泄露扫描
4. **审计**：每次问答记录检索片段 + 剔除结果（qa:retrieval），事后可回溯
5. **红队测试**：对抗用例集（攻击识别 / 误报控制 / 过滤 / 标记 / 输出校验）

## 实现文件

| 文件 | 职责 | 类型 |
|---|---|---|
| `app/services/injection_guard.py` | 检测核心：5 类强特征注入模式（指令覆盖/角色劫持/越狱/泄露试探/间接注入）+ base64/hex 编码绕过解码检测 + `filter_injection` + `scan_answer` | 新增 |
| `app/services/rag/generator.py` | SYSTEM_PROMPT 追加信任声明（`<user_data>` 内内容一律视为数据）；`_format_context` 加 Spotlighting 标记 | 修改 |
| `app/services/rag/pipeline.py` | 检索后 `filter_injection` 剔除恶意 chunk；新增 `_audit_retrieval` 审计（检索片段+剔除结果+输出校验）；生成后 `scan_answer` 输出侧校验 | 修改 |
| `app/services/agent/tools.py` | `search_knowledge_base` 工具返回值包 `<user_data>` 标记（Agent 工具返回同等级防御） | 修改 |
| `app/tasks/document_tasks.py` | 文档解析后扫描全文注入特征，命中记 warning 日志 | 修改 |
| `app/tests/test_injection_defense.py` | 红队测试集 15 例：攻击识别 / 误报控制 / 检索过滤 / Spotlighting / 输出校验 | 新增 |

## 验证结果

- 红队测试 15/15 通过（含 base64 编码绕过识别、正常文档零误报）
- 现有单元测试回归 26/26 通过（无行为破坏）
- 端到端问答正常（真实服务验证：回答 + 引用 + 缓存命中）
- 新审计 `qa:retrieval` 落库（question + snippets + dropped）

## 防御原则

- **附加式**：不改原有逻辑/功能/框架，检测层全部旁路接入，失败不阻断主流程
- **防误报**：只用强特征长短语匹配（"忽略之前的指令"类完整句式），短词不触发
- **双保险**：检索过滤（物理拦截）+ Spotlighting 标记（模型侧心理防御）
- **诚实局限**：关键词防线可被语义级攻击绕过（同义词/外语/句式重组），
  强防御依赖标记 + 模型信任声明；上传扫描为 fail-open 设计（记录不阻断）
