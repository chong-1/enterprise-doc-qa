# Phase 7：企业特性

企业文档智能问答平台第七阶段：多知识库隔离、成员角色权限、操作审计、文档软删除、用户管理后台、系统配置、Redis 限流。

## 阶段目标

- 多知识库隔离：用户只能看到自己拥有/加入/公开的知识库
- 知识库成员管理：owner / editor / viewer 三级角色
- 操作审计日志：上传/删除/问答/权限变更/用户管理全量入库
- 文档软删除：数据库 is_deleted + Chroma 级联删除
- 用户管理后台：用户列表 / 禁用 / 角色分配（管理员）
- 系统配置：LLM 参数运行时生效、KB 级分块参数编辑
- 限流：Redis + ip/user_id 双键，可配置开关

## 新增/修改文件

### 新增

| 文件 | 职责 |
|---|---|
| `app/models/system_config.py` | 系统配置键值表 |
| `app/services/audit_service.py` | 审计埋点 + 客户端 IP 提取 |
| `app/services/system_config_service.py` | 配置读写 + 30s TTL 缓存 |
| `app/api/v1/audit_logs.py` | 审计日志查询 API（管理员） |
| `app/api/v1/system_configs.py` | 系统配置 API（管理员） |
| `app/middleware/rate_limit.py` | Redis 限流中间件 |
| `app/schemas/member.py` `audit.py` `system_config.py` | 对应 Schema |
| `scripts/create_admin.py` | 创建管理员脚本 |
| `scripts/verify_phase7.py` | 35 项端到端验证脚本 |
| `alembic/versions/253b415ce0a3_*.py` | 迁移：kb_members / is_deleted / system_configs |

### 修改

| 文件 | 变更 |
|---|---|
| `app/models/knowledge_base.py` | + KBMemberRole 枚举、KnowledgeBaseMember 成员表 |
| `app/models/document.py` | + is_deleted / deleted_at 软删除字段 |
| `app/core/dependencies.py` | + check_kb_access / require_kb_role / require_admin |
| `app/api/v1/knowledge_bases.py` | 列表隔离 + PATCH/DELETE + 成员管理 |
| `app/api/v1/documents.py` | 角色校验 + 软删除 + 文档列表 |
| `app/api/v1/qa.py` | viewer 校验 + qa:query 审计 |
| `app/api/v1/users.py` | 管理员：列表/禁用/角色分配 |
| `app/db/chroma_store.py` | delete_chunks_by_doc 修复（get ids → delete by ids） |
| `app/services/rag/generator.py` | LLM 参数读系统配置（运行时生效） |
| `app/services/rag/pipeline.py` | rag.top_k 可配置 |
| `app/services/llm/openai_backend.py` | + override_model 运行时模型覆盖 |
| `app/middleware/__init__.py` | 注册限流中间件 |

## 核心设计

### 1. 角色层级与权限模型

```
owner(3) > editor(2) > viewer(1)    超管恒通过

viewer   : 查看 KB、问答、看文档列表/状态
editor   : + 上传/删除文档
owner    : + 改配置、成员管理、删除 KB
公开 KB  : 全员 viewer

owner 不重复入 kb_members 表（knowledge_bases.owner_id 为准）
```

- `require_kb_role("editor")`：依赖工厂，kb_id 取路径参数，内部走 `check_kb_access`
- **踩坑**：upload 接口的 kb_id 是 Form 字段不是路径参数，`require_kb_role` 的 `Path(...)` 解析不到 → 422。改为内联调用 `check_kb_access`。
- 列表隔离 SQL：`owner_id = me OR is_public OR id IN (我的成员 kb)`，并预加载成员角色避免 N+1。

### 2. 文档软删除

```
DELETE /documents/{id}
  ├─ 1. Chroma: get(where=doc_id) → delete(ids)   ← 向量立即消失，检索不再命中
  ├─ 2. 磁盘文件删除
  └─ 3. DB: is_deleted=true + deleted_at          ← 记录保留，可追溯
```

- 列表/详情/状态查询全部过滤 `is_deleted=False`
- Chroma 0.5.23 的 `collection.delete(where=...)` 实际支持，但**返回 None**，无法拿删除数量 → 先 `get` 取 ids 再 `delete(ids=)`（旧代码静默吞异常，导致级联删除可能失败却无感知）

### 3. 审计日志

- `audit_service.log_action(db, user, action, resource_type, resource_id, detail, ip)`
- 覆盖：kb:create/update/delete、kb:member_add/update/remove、document:upload/delete、qa:query（问题截断 100 字）、user:update、config:update
- 管理端 `GET /audit-logs` 分页 + user_id/action/resource_type 过滤，LEFT JOIN 补用户名

### 4. 系统配置

- 存储：`system_configs` 键值表；读侧 30s 内存 TTL 缓存，写侧立即失效
- `llm.model / llm.temperature / llm.max_tokens / rag.top_k` 修改后运行时生效，无需重启
- 模型切换为**存储级配置**：字段可保存/校验，实际推理仍用全局 BGE-M3（16GB 内存只够一个模型，换模型需重新 embedding）
- KB 级 `chunk_size/chunk_overlap/embedding_model` 已有列，PATCH 接口打通（chunk 参数此前已生效）

### 5. 限流中间件

```
身份键: 登录 → user:{id}；匿名 → ip:{ip}
窗口  : 每分钟一个 bucket（rate_limit:{key}:{minute}），INCR + 首次 EXPIRY 120s
开关  : RATE_LIMIT_ENABLED（默认 false，验证时开启）
豁免  : /health、/docs、/redoc、/openapi、/auth/*
降级  : Redis 不可用 → fail-open 不限流
```

## API 一览（新增/变更）

| 方法 | 路径 | 权限 |
|---|---|---|
| GET | /knowledge-bases | 隔离后列表（含 my_role） |
| PATCH | /knowledge-bases/{id} | owner |
| DELETE | /knowledge-bases/{id} | owner（Chroma+文件+DB 级联） |
| GET/POST | /knowledge-bases/{id}/members | owner |
| PATCH/DELETE | /knowledge-bases/{id}/members/{user_id} | owner |
| GET | /documents?kb_id= | viewer（排除软删除） |
| DELETE | /documents/{id} | editor（软删除） |
| POST | /documents/upload | editor（Form kb_id 内联校验） |
| POST | /qa/{kb_id} | viewer |
| GET | /users, /users/roles | 管理员 |
| PATCH | /users/{user_id} | 管理员 |
| GET | /audit-logs | 管理员 |
| GET | /system/configs, PUT /system/configs/{key} | 管理员 |

## 验证结果

自动化脚本 35/35 通过：

```
✅ 隔离：mytest2 列表看不到私有 KB / 直接访问 403 / 上传 403
✅ 成员：加 viewer 可见 → viewer 上传 403 → 升 editor 上传 200
✅ 软删除：处理完成 → 删除前 Chroma 有 chunk → 删除后列表消失/404/Chroma 级联删除
✅ 审计：kb:create / member_add / member_update / document:upload 全记录 + IP
✅ 用户管理：列表 / 禁用后登录 401 / 角色列表
✅ 系统配置：更新 llm.temperature=0.5 / max_tokens=1024 / 非法键被拒
✅ KB 配置：owner 改 chunk_size=256 / editor 改 403
✅ 限流：阈值 5 → 10 连发 [200×5, 429×5]（先清 Redis 计数）
✅ QA：无权限 403 / 真实问答 200（12.3s，qa:query + config:update 审计落库）
```

## 踩坑记录

1. **upload 依赖 422**：`require_kb_role` 依赖声明 `kb_id: Path(...)`，但 upload 的 kb_id 是 Form 字段 → 依赖校验失败返回 422 而非 403 → 内联 `check_kb_access`
2. **裸类型参数**：`admin: User` 无 Annotated → FastAPI 把它当 body 字段报 "Invalid args for response field" → 必须 `admin: CurrentUser`
3. **Chroma delete 返回值**：`delete(where=)` 在 0.5.23 返回 None（旧代码据此静默 pass）→ 改为 get-ids-then-delete
4. **旧用户密码未知**：admin/mytest/mytest2 是 Phase 2 遗留账号，密码对不上 → 重置为已知密码再验证
5. **create_admin.py sys.path**：`python scripts/x.py` 时 sys.path 是 scripts/ 而非 backend/ → 脚本头插 backend 目录
6. **GBK 终端**：✅/❌/中文 print 崩 → 脚本头 `sys.stdout.reconfigure(encoding="utf-8")`

## 下一步

Phase 8：前端界面（Vue 3 + Element Plus：登录、知识库管理、文档管理、问答界面、用户管理、审计日志）
