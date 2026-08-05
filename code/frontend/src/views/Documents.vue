<template>
  <div class="doc-page">
    <div class="page-header">
      <div style="display:flex;align-items:center;gap:8px">
        <el-button text @click="$router.push('/knowledge-bases')">
          <el-icon><ArrowLeft /></el-icon> 返回
        </el-button>
        <h3 style="margin:0">{{ kbName }} — 文档管理</h3>
      </div>
      <el-upload
        :action="`/api/v1/documents/upload`"
        :headers="uploadHeaders"
        :data="{ kb_id: kbId }"
        :before-upload="beforeUpload"
        :on-success="onUploadSuccess"
        :on-error="onUploadError"
        :show-file-list="false"
        accept=".pdf,.docx,.xlsx,.md,.txt"
      >
        <el-button type="primary">
          <el-icon><Upload /></el-icon> 上传文档
        </el-button>
      </el-upload>
    </div>

    <el-table :data="docs" stripe v-loading="loading" style="margin-top:16px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="filename" label="文件名" min-width="1" show-overflow-tooltip />
      <el-table-column label="类型" width="80" align="center">
        <template #default="{ row }">
          <el-tag size="small">{{ row.file_type.toUpperCase() }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="大小" width="100" align="center">
        <template #default="{ row }">
          {{ formatSize(row.file_size) }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110" align="center">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status)" size="small">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="chunk_count" label="分块" width="70" align="center" />
      <el-table-column prop="created_at" label="上传时间" width="170">
        <template #default="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80" align="center" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="danger" text @click="handleDelete(row)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="docs.length === 0 && !loading" style="text-align:center;padding:60px 0;color:#909399">
      <el-icon :size="48"><FolderOpened /></el-icon>
      <p>暂无文档，请上传</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, Upload, Delete, FolderOpened } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const route = useRoute()
const auth = useAuthStore()
const kbId = computed(() => Number(route.params.kbId))
const kbName = ref('')
const docs = ref([])
const loading = ref(false)
let pollTimer = null

const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${auth.token}`,
}))

function formatSize(bytes) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatTime(t) {
  if (!t) return '-'
  return String(t).replace('T', ' ').slice(0, 19)
}

function statusTag(s) {
  if (s === 'completed') return 'success'
  if (s === 'processing') return 'warning'
  if (s === 'failed') return 'danger'
  return 'info'
}
function statusLabel(s) {
  if (s === 'completed') return '已完成'
  if (s === 'processing') return '处理中'
  if (s === 'failed') return '失败'
  if (s === 'pending') return '等待中'
  return s
}

function beforeUpload(file) {
  const ext = file.name.split('.').pop().toLowerCase()
  const allowed = ['pdf', 'docx', 'xlsx', 'md', 'txt']
  if (!allowed.includes(ext)) {
    ElMessage.error(`不支持的文件类型: ${ext}`)
    return false
  }
  if (file.size > 50 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 50MB')
    return false
  }
  return true
}

function onUploadSuccess() {
  ElMessage.success('上传成功，正在处理...')
  fetchDocs()
}

function onUploadError(err) {
  const msg = JSON.parse(err.message || '{}').message || '上传失败'
  ElMessage.error(msg)
}

async function fetchDocs() {
  loading.value = true
  try {
    const res = await api.get('/documents', { params: { kb_id: kbId.value } })
    docs.value = res.data || []
    // 如果有处理中的文档，开启轮询
    const hasProcessing = docs.value.some(d => d.status === 'processing' || d.status === 'pending')
    if (hasProcessing && !pollTimer) {
      pollTimer = setInterval(fetchDocs, 5000)
    } else if (!hasProcessing && pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  } finally {
    loading.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.filename}」？`, '确认删除', { type: 'warning' })
  } catch { return }
  try {
    await api.delete(`/documents/${row.id}`)
    ElMessage.success('已删除')
    await fetchDocs()
  } catch { /* ignore */ }
}

onMounted(async () => {
  // 取 KB 名称
  try {
    const res = await api.get(`/knowledge-bases/${kbId.value}`)
    kbName.value = res.data?.name || `KB#${kbId.value}`
  } catch { kbName.value = `KB#${kbId.value}` }
  await fetchDocs()
})

onUnmounted(() => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
})
</script>

<style scoped>
.page-header { display: flex; align-items: center; justify-content: space-between; }
</style>
