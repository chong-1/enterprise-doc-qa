<template>
  <div class="dashboard">
    <div class="dash-header">
      <div>
        <h2 style="margin:0 0 4px">👋 欢迎回来，{{ auth.user?.username }}</h2>
        <p style="margin:0;color:#909399;font-size:14px">以下是你的知识库使用概况</p>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="20" style="margin-top:20px">
      <el-col :span="8" v-for="card in statCards" :key="card.label">
        <el-card shadow="never" class="stat-card">
          <el-skeleton :loading="loading" animated>
            <template #template>
              <div style="display:flex;align-items:center;gap:16px;padding:8px 0">
                <el-skeleton-item variant="circle" style="width:56px;height:56px" />
                <div style="flex:1"><el-skeleton-item variant="text" style="width:60%" /><el-skeleton-item variant="text" style="width:30%;margin-top:8px" /></div>
              </div>
            </template>
            <template #default>
              <div class="stat-inner">
                <div class="stat-icon" :style="{ background: card.bg }">
                  <span class="stat-emoji">{{ card.icon }}</span>
                </div>
                <div class="stat-body">
                  <div class="stat-num">{{ stats[card.key] }}</div>
                  <div class="stat-label">{{ card.label }}</div>
                </div>
              </div>
            </template>
          </el-skeleton>
        </el-card>
      </el-col>
    </el-row>

    <!-- 最近动态 / 快速入口 -->
    <el-row :gutter="20" style="margin-top:20px">
      <el-col :span="14">
        <el-card shadow="never">
          <template #header>
            <div class="card-title">
              <span>📋 最近动态</span>
              <el-button size="small" text type="primary" @click="$router.push('/audit-logs')" v-if="auth.isAdmin">
                查看全部 →
              </el-button>
            </div>
          </template>
          <el-skeleton :loading="loading" animated :count="3">
            <template #template>
              <div v-for="i in 3" :key="i" style="display:flex;gap:12px;padding:10px 0;align-items:center">
                <el-skeleton-item variant="circle" style="width:32px;height:32px" />
                <div style="flex:1"><el-skeleton-item variant="text" /></div>
              </div>
            </template>
          </el-skeleton>
          <div v-if="!loading && recentLogs.length === 0" style="text-align:center;padding:32px 0;color:#909399">
            <p>暂无动态</p>
          </div>
          <div v-if="!loading && recentLogs.length > 0" class="activity-list">
            <div v-for="log in recentLogs.slice(0, 6)" :key="log.id" class="activity-item">
              <el-tag :type="actionTag(log.action)" size="small" effect="plain">
                {{ actionLabel(log.action) }}
              </el-tag>
              <span class="act-detail">{{ detailText(log) }}</span>
              <span class="act-time">{{ log.created_at?.slice(11, 19) }}</span>
            </div>
          </div>
          <div v-if="!loading && !auth.isAdmin" class="quick-links">
            <div class="quick-link" @click="$router.push('/knowledge-bases')">
              <span class="ql-icon">📁</span>
              <span>管理知识库</span>
              <el-icon><ArrowRight /></el-icon>
            </div>
            <div class="quick-link" @click="$router.push('/qa')">
              <span class="ql-icon">💬</span>
              <span>开始问答</span>
              <el-icon><ArrowRight /></el-icon>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="10">
        <el-card shadow="never">
          <template #header>
            <span class="card-title">📊 我的知识库</span>
          </template>
          <el-skeleton :loading="loading" animated :count="2">
            <template #template>
              <div v-for="i in 2" :key="i" style="padding:8px 0"><el-skeleton-item variant="text" style="width:100%" /><el-skeleton-item variant="text" style="width:40%;margin-top:4px" /></div>
            </template>
          </el-skeleton>
          <div v-if="!loading && topKbs.length === 0" style="text-align:center;padding:24px 0;color:#909399">
            <p>还没创建知识库</p>
            <el-button size="small" type="primary" @click="$router.push('/knowledge-bases')">去创建</el-button>
          </div>
          <div v-if="!loading && topKbs.length > 0" class="kb-list">
            <div v-for="kb in topKbs" :key="kb.id" class="kb-item" @click="$router.push(`/knowledge-bases/${kb.id}/documents`)">
              <div class="kb-item-icon">📄</div>
              <div class="kb-item-body">
                <div class="kb-item-name">{{ kb.name }}</div>
                <div class="kb-item-meta">
                  <span>{{ kb.document_count }} 文档</span>
                  <el-tag :type="roleTag(kb.my_role)" size="small" effect="plain">{{ roleLabel(kb.my_role) }}</el-tag>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ArrowRight } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const auth = useAuthStore()
const loading = ref(true)

const stats = reactive({ kbCount: 0, docCount: 0, qaCount: 0 })
const recentLogs = ref([])
const topKbs = ref([])

// 注意：value 不在此快照，模板里通过 stats[card.key] 动态读取，避免初始值 0 被固化
const statCards = [
  { key: 'kbCount', icon: '📁', label: '知识库', bg: '#e6f0ff' },
  { key: 'docCount', icon: '📄', label: '文档总数', bg: '#e6ffe6' },
  { key: 'qaCount', icon: '💬', label: '问答次数', bg: '#fff3e6' },
]

function actionTag(a) {
  if (a?.startsWith('kb:')) return 'primary'
  if (a?.startsWith('document:')) return 'success'
  if (a?.startsWith('qa:')) return 'warning'
  return 'info'
}
function actionLabel(a) {
  const map = { 'kb:create': '创建KB', 'kb:update': '更新KB', 'document:upload': '上传文档', 'document:delete': '删除文档', 'qa:query': '问答', 'user:update': '用户变更', 'config:update': '配置变更' }
  return map[a] || a || '未知'
}
function detailText(row) {
  if (!row.detail) return ''
  try {
    const d = JSON.parse(row.detail)
    if (d.name) return `"${d.name}"`
    if (d.filename) return d.filename
    if (d.question) return d.question
    if (d.target) return `用户: ${d.target}`
    return ''
  } catch { return (row.detail || '').slice(0, 60) }
}
function roleTag(r) { return r === 'owner' ? 'danger' : r === 'editor' ? 'warning' : 'info' }
function roleLabel(r) { return r === 'owner' ? '拥有者' : r === 'editor' ? '编辑' : '查看' }

onMounted(async () => {
  // KB 列表（所有用户）
  try {
    const kRes = await api.get('/knowledge-bases')
    const kbs = kRes.data || []
    stats.kbCount = kbs.length
    stats.docCount = kbs.reduce((s, k) => s + (k.document_count || 0), 0)
    topKbs.value = kbs.slice(0, 5)
  } catch {}
  // 审计（仅管理员）
  if (auth.isAdmin) {
    try {
      const aRes = await api.get('/audit-logs', { params: { page_size: 10 } })
      stats.qaCount = aRes.data?.total || 0
      recentLogs.value = aRes.data?.items || []
    } catch {}
  }
  loading.value = false
})
</script>

<style scoped>
.dash-header { display: flex; align-items: center; justify-content: space-between; }
.stat-card { border-radius: 12px; border: none; transition: box-shadow .3s; }
.stat-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,.08); }
.stat-inner { display: flex; align-items: center; gap: 18px; padding: 4px 0; }
.stat-icon { width: 56px; height: 56px; border-radius: 14px; display: flex; align-items: center; justify-content: center; }
.stat-emoji { font-size: 26px; }
.stat-num { font-size: 30px; font-weight: 700; color: #303133; line-height: 1.2; }
.stat-label { font-size: 14px; color: #909399; margin-top: 2px; }
.card-title { font-weight: 600; display: flex; align-items: center; justify-content: space-between; }
.activity-list { display: flex; flex-direction: column; }
.activity-item { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid #f5f5f5; }
.act-detail { flex: 1; font-size: 13px; color: #606266; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.act-time { font-size: 12px; color: #c0c4cc; }
.quick-links { margin-top: 16px; display: flex; flex-direction: column; gap: 8px; }
.quick-link { display: flex; align-items: center; gap: 10px; padding: 12px 16px; background: #f5f7fa; border-radius: 8px; cursor: pointer; transition: background .2s; font-size: 14px; color: #303133; }
.quick-link:hover { background: #e6f0ff; }
.ql-icon { font-size: 20px; }
.kb-item { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid #f5f5f5; cursor: pointer; transition: background .2s; border-radius: 6px; padding: 8px; }
.kb-item:hover { background: #f5f7fa; }
.kb-item-icon { font-size: 24px; }
.kb-item-name { font-size: 14px; font-weight: 500; color: #303133; }
.kb-item-meta { display: flex; align-items: center; gap: 8px; margin-top: 4px; font-size: 12px; color: #909399; }
</style>
