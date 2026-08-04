# Phase 8：前端界面

企业文档智能问答平台第八阶段：Vue 3 + Element Plus 管理后台 + 问答界面。

## 阶段目标

- 登录/注册页
- 首页仪表盘（知识库数/文档数/问答次数统计）
- 知识库管理（列表/创建/编辑/删除 + 成员管理弹窗）
- 文档管理（上传/列表/状态自动轮询/删除）
- 智能问答（对话列表 + SSE 流式聊天 + 引用展示 + Agent 模式切换）
- 用户管理（管理员：列表/搜索/禁用/角色分配）
- 审计日志（管理员：分页 + 操作类型/资源类型筛选）

## 技术栈

| 层 | 选型 |
|---|---|
| 框架 | Vue 3 (Composition API) |
| 构建 | Vite 6 |
| UI 库 | Element Plus 2.9（中文 locale） |
| 状态管理 | Pinia 2 |
| 路由 | Vue Router 4（导航守卫：未登录→登录页，非管理员→首页） |
| HTTP | Axios（自动带 token + 401 跳登录） |
| SSE 流式 | Fetch ReadableStream 解析 SSE |

## 文件清单（13 个源文件，~1400 行）

```
frontend/
├── index.html                  ← 入口 HTML
├── package.json                ← 依赖声明（vue/vue-router/pinia/element-plus/axios/vite）
├── vite.config.js              ← Vite 配置 + /api → localhost:8000 代理
└── src/
    ├── main.js                 ← Vue 应用入口（挂载 ElementPlus/Pinia/Router）
    ├── App.vue                 ← 根组件
    ├── api/
    │   └── index.js            ← axios 封装（请求拦截器带 token，响应拦截器统一错误/401 跳转）
    ├── router/
    │   └── index.js            ← 7 条路由 + 导航守卫
    ├── stores/
    │   └── auth.js             ← Pinia 认证状态（登录/注册/登出/取用户信息）
    └── views/
        ├── Layout.vue          ← 主布局（侧边栏+顶栏：管理员看到用户管理/审计日志入口）
        ├── Login.vue           ← 登录/注册（Tab 切换，表单校验，token 存 localStorage）
        ├── Dashboard.vue       ← 仪表盘（3 个统计卡片 + 管理员最近动态表）
        ├── KnowledgeBases.vue  ← 知识库管理（列表/创建/编辑/删除 + 成员管理弹窗）
        ├── Documents.vue       ← 文档管理（上传+类型大小校验/列表/状态 5s 轮询/删除）
        ├── QAChat.vue          ← 智能问答（KB选择+对话列表+SSE流式聊天+引用+Agent模式）
        ├── Users.vue           ← 用户管理（管理员：列表/搜索/编辑：禁用+超管+角色分配）
        └── AuditLogs.vue       ← 审计日志（管理员：分页+操作类型+资源类型筛选）
```

## 路由设计

| 路径 | 页面 | 权限 |
|---|---|---|
| `/login` | 登录/注册 | 游客 |
| `/dashboard` | 首页仪表盘 | 登录用户 |
| `/knowledge-bases` | 知识库管理 | 登录用户 |
| `/knowledge-bases/:kbId/documents` | 文档管理 | 登录用户 |
| `/qa` | 智能问答 | 登录用户 |
| `/users` | 用户管理 | 管理员 |
| `/audit-logs` | 审计日志 | 管理员 |

## npm 依赖安装

```bash
cd frontend
npm config set registry https://registry.npmmirror.com
npm install
```

## 启动方式

```bash
cd frontend
npx vite --host 0.0.0.0 --port 5173
```

浏览器打开 `http://localhost:5173`

## 验证结果

- 全部 7 个页面 Vite 编译 200
- 登录/注册 API 代理到后端 8000 端口正常
- SSE 流式问答可用（Fetch ReadableStream 解析后端 SSE 事件）

## 下一步

Phase 9：测试与优化（pytest 单元测试 + API 集成测试 + RAG 评估）
