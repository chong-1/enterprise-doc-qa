<template>
  <el-container class="layout">
    <el-aside width="230px" class="aside">
      <div class="logo" @click="$router.push('/dashboard')">
        <span class="logo-icon">📚</span>
        <div>
          <div class="logo-title">EQA 平台</div>
          <div class="logo-sub">企业文档智能问答</div>
        </div>
      </div>

      <el-menu
        :default-active="activeMenu"
        router
        background-color="#1d1e2c"
        text-color="#8b8fa3"
        active-text-color="#fff"
        class="side-menu"
      >
        <el-menu-item index="/dashboard">
          <template #title>
            <el-icon><DataAnalysis /></el-icon>
            <span>仪表盘</span>
          </template>
        </el-menu-item>

        <el-menu-item index="/knowledge-bases">
          <template #title>
            <el-icon><Folder /></el-icon>
            <span>知识库</span>
          </template>
        </el-menu-item>

        <el-menu-item index="/qa">
          <template #title>
            <el-icon><ChatDotRound /></el-icon>
            <span>智能问答</span>
            <el-badge :value="'new'" class="menu-badge" />
          </template>
        </el-menu-item>

        <div v-if="auth.isAdmin" class="menu-divider">
          <span>管理</span>
        </div>

        <template v-if="auth.isAdmin">
          <el-menu-item index="/users">
            <template #title>
              <el-icon><User /></el-icon>
              <span>用户管理</span>
            </template>
          </el-menu-item>
          <el-menu-item index="/audit-logs">
            <template #title>
              <el-icon><Document /></el-icon>
              <span>审计日志</span>
            </template>
          </el-menu-item>
        </template>
      </el-menu>

      <div class="aside-footer">
        <div class="user-info">
          <span class="user-dot" :class="{ admin: auth.isAdmin }" />
          <span class="user-name">{{ auth.user?.username }}</span>
          <el-tag v-if="auth.isAdmin" type="danger" size="small" effect="dark">超管</el-tag>
        </div>
        <el-button text @click="auth.logout()" class="logout-btn">
          <el-icon><SwitchButton /></el-icon>
        </el-button>
      </div>
    </el-aside>

    <el-container>
      <el-header class="header">
        <!-- 面包屑 -->
        <el-breadcrumb separator="/">
          <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
          <el-breadcrumb-item v-if="route.meta.title && route.path !== '/dashboard'">
            {{ route.meta.title }}
          </el-breadcrumb-item>
        </el-breadcrumb>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const auth = useAuthStore()

const activeMenu = computed(() => {
  if (route.path.startsWith('/knowledge-bases/') && !route.path.endsWith('/documents')) return '/knowledge-bases'
  if (route.path.includes('/documents')) return '/knowledge-bases'
  return route.path
})
</script>

<style scoped>
/* ====== 布局 ====== */
.layout { height: 100vh; }
.aside {
  background: #1d1e2c;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ====== Logo ====== */
.logo {
  height: 64px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 20px;
  cursor: pointer;
  border-bottom: 1px solid rgba(255,255,255,.06);
}
.logo-icon { font-size: 24px; }
.logo-title { font-size: 16px; font-weight: 700; color: #fff; letter-spacing: 1px; }
.logo-sub { font-size: 10px; color: #8b8fa3; margin-top: 1px; }

/* ====== 菜单 ====== */
.side-menu { border-right: none; flex: 1; padding: 8px 0; }
.side-menu .el-menu-item {
  height: 44px;
  line-height: 44px;
  margin: 2px 12px;
  border-radius: 8px;
  font-size: 14px;
  transition: all .2s;
}
.side-menu .el-menu-item:hover { background: rgba(255,255,255,.06); }
.side-menu .el-menu-item.is-active {
  background: linear-gradient(135deg, #409EFF, #337ecc);
  color: #fff !important;
}
.side-menu .el-menu-item.is-active .el-icon { color: #fff !important; }
.menu-badge { margin-left: auto; }
.menu-divider {
  padding: 16px 20px 6px;
  font-size: 11px;
  color: #5a5d6e;
  text-transform: uppercase;
  letter-spacing: 1px;
}

/* ====== 底栏 ====== */
.aside-footer {
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-top: 1px solid rgba(255,255,255,.06);
}
.user-info { display: flex; align-items: center; gap: 6px; }
.user-dot { width: 8px; height: 8px; border-radius: 50%; background: #67c23a; }
.user-dot.admin { background: #f56c6c; }
.user-name { font-size: 13px; color: #c8c9d0; max-width: 80px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.logout-btn { color: #8b8fa3 !important; }

/* ====== 顶栏 ====== */
.header {
  height: 52px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  padding: 0 24px;
}

/* ====== 内容区 ====== */
.main {
  background: #f5f7fa;
  min-height: calc(100vh - 52px);
  padding: 24px;
}
</style>
