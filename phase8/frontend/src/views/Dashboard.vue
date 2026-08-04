<template>
  <div class="dashboard">
    <h2 style="margin:0 0 24px 0">欢迎回来，{{ auth.user?.username }}</h2>

    <el-row :gutter="20">
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-inner">
            <div class="stat-icon" style="background:#e6f7ff">
              <el-icon :size="32" color="#1890ff"><Folder /></el-icon>
            </div>
            <div class="stat-body">
              <div class="stat-num">{{ stats.kbCount }}</div>
              <div class="stat-label">知识库</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-inner">
            <div class="stat-icon" style="background:#f6ffed">
              <el-icon :size="32" color="#52c41a"><Document /></el-icon>
            </div>
            <div class="stat-body">
              <div class="stat-num">{{ stats.docCount }}</div>
              <div class="stat-label">文档总数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-inner">
            <div class="stat-icon" style="background:#fff7e6">
              <el-icon :size="32" color="#fa8c16"><ChatDotRound /></el-icon>
            </div>
            <div class="stat-body">
              <div class="stat-num">{{ stats.qaCount }}</div>
              <div class="stat-label">问答次数</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top:24px" shadow="never">
      <template #header>
        <span style="font-weight:600">最近动态</span>
      </template>
      <el-table :data="recentLogs" stripe size="default" v-loading="loading">
        <el-table-column label="时间" prop="created_at" width="180" />
        <el-table-column label="用户" prop="username" width="120" />
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-tag :type="actionTag(row.action)" size="small">{{ row.action }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="详情" min-width="1">
          <template #default="{ row }">
            <span style="color:#909399">{{ detailText(row) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const auth = useAuthStore()
const loading = ref(false)

const stats = reactive({ kbCount: 0, docCount: 0, qaCount: 0 })
const recentLogs = ref([])

function actionTag(action) {
  if (action.startsWith('kb:')) return 'primary'
  if (action.startsWith('document:')) return 'success'
  if (action.startsWith('qa:')) return 'warning'
  if (action.startsWith('user:')) return 'danger'
  return 'info'
}

function detailText(row) {
  if (!row.detail) return '-'
  try {
    const d = JSON.parse(row.detail)
    if (d.name) return `"${d.name}"`
    if (d.filename) return d.filename
    if (d.question) return d.question
    if (d.target) return `用户: ${d.target}`
    return JSON.stringify(d).slice(0, 60)
  } catch {
    return row.detail.slice(0, 80)
  }
}

onMounted(async () => {
  loading.value = true
  try {
    const kbRes = await api.get('/knowledge-bases')
    const kbs = kbRes.data || []
    stats.kbCount = kbs.length
    stats.docCount = kbs.reduce((sum, kb) => sum + (kb.document_count || 0), 0)
  } catch { /* ignore */ }

  // 管理员额外拉审计日志
  if (auth.isAdmin) {
    try {
      const auditRes = await api.get('/audit-logs', { params: { page_size: 20 } })
      stats.qaCount = auditRes.data.total || 0
      recentLogs.value = auditRes.data.items || []
    } catch { /* ignore */ }
  }
  loading.value = false
})
</script>

<style scoped>
.stat-card { cursor: default; }
.stat-inner { display: flex; align-items: center; gap: 20px; }
.stat-icon { width: 64px; height: 64px; border-radius: 12px; display: flex; align-items: center; justify-content: center; }
.stat-num { font-size: 28px; font-weight: 700; color: #303133; line-height: 1.2; }
.stat-label { font-size: 14px; color: #909399; margin-top: 4px; }
</style>
