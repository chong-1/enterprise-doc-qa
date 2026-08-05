<template>
  <div>
    <div class="page-header">
      <h3 style="margin:0">审计日志</h3>
    </div>

    <div style="margin-top:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
      <el-select v-model="filters.action" placeholder="操作类型" clearable style="width:180px" @change="fetchLogs">
        <el-option label="知识库创建" value="kb:create" />
        <el-option label="知识库更新" value="kb:update" />
        <el-option label="知识库删除" value="kb:delete" />
        <el-option label="成员添加" value="kb:member_add" />
        <el-option label="成员更新" value="kb:member_update" />
        <el-option label="成员移除" value="kb:member_remove" />
        <el-option label="文档上传" value="document:upload" />
        <el-option label="文档删除" value="document:delete" />
        <el-option label="问答查询" value="qa:query" />
        <el-option label="用户更新" value="user:update" />
        <el-option label="配置更新" value="config:update" />
      </el-select>
      <el-select v-model="filters.resource_type" placeholder="资源类型" clearable style="width:140px" @change="fetchLogs">
        <el-option label="知识库" value="kb" />
        <el-option label="文档" value="document" />
        <el-option label="问答" value="qa" />
        <el-option label="用户" value="user" />
      </el-select>
      <el-button @click="filters = {}; fetchLogs()">重置</el-button>
    </div>

    <el-table :data="logs" stripe v-loading="loading" style="margin-top:16px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="created_at" label="时间" width="170" />
      <el-table-column prop="username" label="操作人" width="120">
        <template #default="{ row }">
          {{ row.username || `ID:${row.user_id}` }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-tag :type="actionTag(row.action)" size="small">{{ row.action }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="resource_type" label="资源" width="80" align="center" />
      <el-table-column prop="resource_id" label="资源ID" width="80" align="center" />
      <el-table-column label="详情" min-width="1">
        <template #default="{ row }">
          <span style="color:#909399;font-size:13px">{{ detailText(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="ip_address" label="IP" width="130" />
    </el-table>

    <div style="margin-top:16px;text-align:right">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="fetchLogs"
        background
      />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '../api'

const loading = ref(false)
const logs = ref([])
const page = ref(1)
const pageSize = ref(30)
const total = ref(0)

const filters = reactive({
  action: '',
  resource_type: '',
})

function actionTag(action) {
  if (action?.startsWith('kb:')) return 'primary'
  if (action?.startsWith('document:')) return 'success'
  if (action?.startsWith('qa:')) return 'warning'
  if (action?.startsWith('user:')) return 'danger'
  return 'info'
}

function detailText(row) {
  if (!row.detail) return '-'
  try {
    const d = JSON.parse(row.detail)
    if (d.name) return `"${d.name}"`
    if (d.filename) return d.filename
    if (d.question) return d.question
    if (d.changed) {
      const keys = Object.keys(d.changed)
      return `修改了: ${keys.join(', ')}`
    }
    if (d.target) return `用户: ${d.target}`
    if (d.username) return `用户: ${d.username}，角色: ${d.role || '?'}`
    return JSON.stringify(d).slice(0, 80)
  } catch {
    return row.detail.slice(0, 80)
  }
}

async function fetchLogs() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filters.action) params.action = filters.action
    if (filters.resource_type) params.resource_type = filters.resource_type
    const res = await api.get('/audit-logs', { params })
    logs.value = res.data?.items || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

onMounted(fetchLogs)
</script>

<style scoped>
.page-header { display: flex; align-items: center; justify-content: space-between; }
</style>
