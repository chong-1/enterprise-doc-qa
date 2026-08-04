<template>
  <div class="kb-page">
    <div class="page-header">
      <h3 style="margin:0">知识库管理</h3>
      <el-button type="primary" @click="openCreate">创建知识库</el-button>
    </div>

    <el-table :data="kbs" stripe v-loading="loading" style="margin-top:16px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="名称" min-width="1">
        <template #default="{ row }">
          <el-link type="primary" @click="$router.push(`/knowledge-bases/${row.id}/documents`)">
            {{ row.name }}
          </el-link>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" min-width="1" show-overflow-tooltip />
      <el-table-column label="公开" width="70" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_public ? 'success' : 'info'" size="small">
            {{ row.is_public ? '公开' : '私有' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="我的角色" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="roleTag(row.my_role)" size="small">{{ roleLabel(row.my_role) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="document_count" label="文档数" width="80" align="center" />
      <el-table-column label="操作" width="320" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="$router.push(`/knowledge-bases/${row.id}/documents`)">
            <el-icon><Document /></el-icon> 文档
          </el-button>
          <template v-if="row.my_role === 'owner'">
            <el-button size="small" type="warning" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" @click="openMembers(row)">成员</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </template>
      </el-table-column>
    </el-table>

    <!-- ===== 创建/编辑弹窗 ===== -->
    <el-dialog
      v-model="dialog.visible"
      :title="dialog.isEdit ? '编辑知识库' : '创建知识库'"
      width="560px"
      @closed="resetForm"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" maxlength="200" clearable />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="2" maxlength="500" />
        </el-form-item>
        <template v-if="!dialog.isEdit">
          <el-form-item label="Embedding 模型">
            <el-select v-model="form.embedding_model" style="width:100%">
              <el-option label="BAAI/bge-m3" value="BAAI/bge-m3" />
            </el-select>
          </el-form-item>
          <el-form-item label="分块大小">
            <el-input-number v-model="form.chunk_size" :min="128" :max="2048" :step="64" />
          </el-form-item>
          <el-form-item label="分块重叠">
            <el-input-number v-model="form.chunk_overlap" :min="0" :max="512" :step="16" />
          </el-form-item>
          <el-form-item label="公开">
            <el-switch v-model="form.is_public" />
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item label="公开">
            <el-switch v-model="form.is_public" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- ===== 成员管理弹窗 ===== -->
    <el-dialog v-model="memberDialog.visible" title="成员管理" width="500px">
      <div style="margin-bottom:12px;display:flex;gap:8px">
        <el-input-number v-model="memberForm.user_id" :min="1" placeholder="用户ID" style="flex:1" />
        <el-select v-model="memberForm.role" style="width:120px">
          <el-option label="viewer" value="viewer" />
          <el-option label="editor" value="editor" />
        </el-select>
        <el-button type="primary" :loading="addingMember" @click="addMember">添加</el-button>
      </div>
      <el-table :data="members" stripe size="small" max-height="300">
        <el-table-column prop="user_id" label="用户ID" width="80" />
        <el-table-column prop="username" label="用户名" />
        <el-table-column label="角色" width="180">
          <template #default="{ row }">
            <el-select v-model="row.role" size="small" @change="(val) => changeRole(row, val)">
              <el-option label="viewer" value="viewer" />
              <el-option label="editor" value="editor" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="70" align="center">
          <template #default="{ row }">
            <el-button size="small" type="danger" text @click="removeMember(row)">移除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const loading = ref(false)
const saving = ref(false)
const kbs = ref([])
const formRef = ref(null)

const dialog = reactive({ visible: false, isEdit: false, kbId: null })
const form = reactive({
  name: '', description: '', embedding_model: 'BAAI/bge-m3',
  chunk_size: 512, chunk_overlap: 64, is_public: false,
})
const rules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
}

// ------ 成员管理 ------
const memberDialog = reactive({ visible: false, kbId: null })
const members = ref([])
const memberForm = reactive({ user_id: 1, role: 'viewer' })
const addingMember = ref(false)

function roleTag(role) {
  if (role === 'owner') return 'danger'
  if (role === 'editor') return 'warning'
  return 'info'
}
function roleLabel(role) {
  if (role === 'owner') return '拥有者'
  if (role === 'editor') return '编辑者'
  return '查看者'
}

async function fetchKBs() {
  loading.value = true
  try {
    const res = await api.get('/knowledge-bases')
    kbs.value = res.data || []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  dialog.isEdit = false
  dialog.visible = true
}

function openEdit(row) {
  dialog.isEdit = true
  dialog.kbId = row.id
  form.name = row.name
  form.description = row.description || ''
  form.is_public = row.is_public
  dialog.visible = true
}

function resetForm() {
  formRef.value?.resetFields()
  Object.assign(form, {
    name: '', description: '', embedding_model: 'BAAI/bge-m3',
    chunk_size: 512, chunk_overlap: 64, is_public: false,
  })
  dialog.kbId = null
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (dialog.isEdit) {
      await api.patch(`/knowledge-bases/${dialog.kbId}`, {
        name: form.name, description: form.description || null, is_public: form.is_public,
      })
      ElMessage.success('更新成功')
    } else {
      await api.post('/knowledge-bases', form)
      ElMessage.success('创建成功')
    }
    dialog.visible = false
    await fetchKBs()
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除知识库「${row.name}」？文档和成员将一并删除。`, '删除确认', {
      type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消',
    })
  } catch { return }
  try {
    await api.delete(`/knowledge-bases/${row.id}`)
    ElMessage.success('已删除')
    await fetchKBs()
  } catch { /* 拦截器已提示 */ }
}

// ------ 成员管理 ------
async function openMembers(row) {
  memberDialog.kbId = row.id
  try {
    const res = await api.get(`/knowledge-bases/${row.id}/members`)
    members.value = res.data || []
  } catch {
    members.value = []
  }
  memberDialog.visible = true
}

async function addMember() {
  addingMember.value = true
  try {
    await api.post(`/knowledge-bases/${memberDialog.kbId}/members`, {
      user_id: memberForm.user_id, role: memberForm.role,
    })
    ElMessage.success('已添加')
    memberForm.user_id = memberForm.user_id + 1
    // 刷新列表
    const res = await api.get(`/knowledge-bases/${memberDialog.kbId}/members`)
    members.value = res.data || []
  } finally {
    addingMember.value = false
  }
}

async function changeRole(row, newRole) {
  try {
    await api.patch(`/knowledge-bases/${memberDialog.kbId}/members/${row.user_id}`, { role: newRole })
    ElMessage.success('角色已更新')
  } catch {
    // 回滚显示
    const res = await api.get(`/knowledge-bases/${memberDialog.kbId}/members`)
    members.value = res.data || []
  }
}

async function removeMember(row) {
  try {
    await ElMessageBox.confirm(`确定移除用户 ${row.username || row.user_id}？`, '确认', { type: 'warning' })
  } catch { return }
  try {
    await api.delete(`/knowledge-bases/${memberDialog.kbId}/members/${row.user_id}`)
    ElMessage.success('已移除')
    members.value = members.value.filter(m => m.user_id !== row.user_id)
  } catch { /* ignore */ }
}

onMounted(fetchKBs)
</script>

<style scoped>
.page-header { display: flex; align-items: center; justify-content: space-between; }
</style>
