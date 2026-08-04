<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo" @click="$router.push('/dashboard')">
        <span class="logo-text">📚 EQA 平台</span>
      </div>
      <el-menu
        :default-active="route.path"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataAnalysis /></el-icon>
          <span>首页</span>
        </el-menu-item>
        <el-menu-item index="/knowledge-bases">
          <el-icon><Folder /></el-icon>
          <span>知识库管理</span>
        </el-menu-item>
        <el-menu-item index="/qa">
          <el-icon><ChatDotRound /></el-icon>
          <span>智能问答</span>
        </el-menu-item>
        <template v-if="auth.isAdmin">
          <el-menu-item index="/users">
            <el-icon><User /></el-icon>
            <span>用户管理</span>
          </el-menu-item>
          <el-menu-item index="/audit-logs">
            <el-icon><Document /></el-icon>
            <span>审计日志</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          <span class="page-title">{{ route.meta.title || '' }}</span>
        </div>
        <div class="header-right">
          <el-tag v-if="auth.isAdmin" type="danger" size="small">管理员</el-tag>
          <span class="username">{{ auth.user?.username }}</span>
          <el-button text @click="auth.logout()">退出</el-button>
        </div>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const auth = useAuthStore()
</script>

<style scoped>
.layout { height: 100vh; }
.aside { background: #304156; overflow-y: auto; }
.logo { height: 60px; display: flex; align-items: center; justify-content: center; cursor: pointer; }
.logo-text { color: #fff; font-size: 18px; font-weight: bold; letter-spacing: 2px; }
.header { background: #fff; border-bottom: 1px solid #e6e6e6; display: flex; align-items: center; justify-content: space-between; padding: 0 24px; height: 60px; }
.header-left { display: flex; align-items: center; }
.page-title { font-size: 16px; font-weight: 600; color: #303133; }
.header-right { display: flex; align-items: center; gap: 12px; }
.username { color: #606266; }
.main { background: #f0f2f5; min-height: calc(100vh - 60px); padding: 24px; }
</style>
