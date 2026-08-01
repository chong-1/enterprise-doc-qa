# Phase 2：JWT 认证 + RBAC 权限

企业文档智能问答平台第二阶段：解决"你是谁"（认证）和"你能干什么"（授权）。

## 阶段目标

- 密码哈希 + JWT 无状态认证（Access 60min / Refresh 7day 双 Token）
- 注册 / 登录 / Token 刷新 / 获取当前用户四个 API
- RBAC 三级权限：User ↔ Role ↔ Permission（多对多）
- 权限校验依赖工厂：`require_permission("document:upload")`
- 初始化默认角色：admin（全部权限）/ editor（上传+问答）/ viewer（查看+问答）

## 实现文件

| 文件 | 职责 | 类型 |
|---|---|---|
| `backend/app/services/auth_service.py` | 注册（默认 viewer 角色）/ 登录 / Token 对签发与刷新 | 新增 |
| `backend/app/core/dependencies.py` | get_current_user（加载角色权限）、require_permission/require_role 依赖工厂 | 修改 |
| `backend/app/api/v1/auth.py` | POST /auth/register、/auth/login、/auth/refresh | 修改 |
| `backend/app/api/v1/users.py` | GET /users/me（含角色列表） | 修改 |
| `backend/app/schemas/user.py` | UserResponse 增加 roles 字段 + from_user 工厂 | 修改 |
| `backend/app/models/base.py` | TimestampMixin 修复：SQL 侧默认值 → Python 侧，避免 async lazy load 报 MissingGreenlet | 修改 |
| `backend/app/core/config.py` | 连接池回收周期 3600s → 600s | 修改 |
| `backend/app/db/session.py` | 连接池加 pre_ping 探活，修复公网僵尸连接 | 修改 |
| `backend/tests/test_security.py` | 密码哈希 + JWT 单元测试 8 例 | 新增 |

## 核心设计

### 1. 认证流程

```
注册 → bcrypt 哈希 → 写库（默认绑定 viewer 角色）
登录 → 验密码 → 签发 access_token(60min) + refresh_token(7day)
请求 → Bearer token → 验签 + 验 type=access → 查库加载用户+角色+权限
刷新 → 验 refresh token → 换新 Token 对（用户无需重新登录）
```

JWT 无状态：服务端不存 token，验签即可。payload 含 `sub`(用户ID) / `iat`(签发时间) / `exp`(过期时间) / `type`(防 access/refresh 混用)。

### 2. RBAC

```
users ──< user_roles >── roles ──< role_permissions >── permissions(code)
```

`require_permission(code)` 是依赖工厂（闭包捕获 code），嵌套依赖 `get_current_user`，
权限判定 = 集合运算：`{p.code for r in user.roles for p in r.permissions}`，superuser 自动放行。

## 验证结果（curl 全流程 9 项通过）

| 场景 | 结果 |
|---|---|
| 注册新用户 | 200，roles=["viewer"] |
| 重复注册 | 409 用户名或邮箱已存在 |
| 登录 | 200，返回 Token 对 |
| /users/me + token | 200，返回用户信息 |
| 错误密码 / 无 token | 401 |
| refresh 换新对 | 200 |
| access 冒充 refresh | 401（type 校验） |
| admin 登录 | 200 |

## 踩坑记录（面试素材）

1. **MissingGreenlet**：`default=func.now()`（SQL 侧默认值）flush 后列被标记 expired，
   序列化时触发 lazy load，async 会话禁止 → 改 Python 侧 `datetime.now`（影响后续所有 Phase）
2. **公网僵尸连接**：本机 → 云端 MySQL 的长连接被中间设备静默掐断，连接池不知情，
   隔段时间请求报 `2013 Lost connection` → 加 `pool_pre_ping=True` 取连接前探活
3. **Windows 环境**：Git Bash 默认 PATH 指向 base conda，需用 `envs/eqa/python.exe`

## 如何运行

```bash
# 前提：云端 MySQL + Redis 已启动（见 Phase 1），本机 eqa 环境已装依赖
cd backend
/c/Users/86150/anaconda3/envs/eqa/python.exe -m uvicorn app.main:app --port 8000

# 验证
curl -X POST http://localhost:8000/api/v1/auth/register -H "Content-Type: application/json" \
  -d '{"username":"demo","email":"demo@test.com","password":"demo123456"}'
curl -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"demo123456"}'
```

Swagger 文档：http://localhost:8000/api/v1/docs

## 里程碑

- 提交 `32bc9f3` feat(phase2): 实现 JWT 认证和 RBAC 权限
- 提交 `8230dc5` fix: MySQL 连接池加 pre_ping 探活

下一步：**Phase 3 文档上传 + 多格式解析 + 智能分块**（开始安装 AI 重依赖：torch / FlagEmbedding / chromadb / PaddleOCR）
