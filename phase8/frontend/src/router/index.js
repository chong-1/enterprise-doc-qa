import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { guest: true },
  },
  {
    path: '/',
    component: () => import('../views/Layout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('../views/Dashboard.vue'),
        meta: { title: '首页' },
      },
      {
        path: 'knowledge-bases',
        name: 'KnowledgeBases',
        component: () => import('../views/KnowledgeBases.vue'),
        meta: { title: '知识库管理' },
      },
      {
        path: 'knowledge-bases/:kbId/documents',
        name: 'Documents',
        component: () => import('../views/Documents.vue'),
        meta: { title: '文档管理' },
      },
      {
        path: 'qa',
        name: 'QA',
        component: () => import('../views/QAChat.vue'),
        meta: { title: '智能问答' },
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('../views/Users.vue'),
        meta: { title: '用户管理', admin: true },
      },
      {
        path: 'audit-logs',
        name: 'AuditLogs',
        component: () => import('../views/AuditLogs.vue'),
        meta: { title: '审计日志', admin: true },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const auth = useAuthStore()
  if (to.meta.guest) {
    // 已登录访问登录页 → 跳首页
    if (auth.token) return next('/dashboard')
    return next()
  }
  // 未登录 → 跳登录页
  if (!auth.token) return next('/login')
  // 管理员页面校验
  if (to.meta.admin && !auth.user?.is_superuser) return next('/dashboard')
  next()
})

export default router
