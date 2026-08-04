<template>
  <div>
    <div class="page-header">
      <h3 style="margin:0">用户管理</h3>
    </div>

    <div style="margin-top:16px;display:flex;gap:12px;align-items:center">
      <el-input v-model="keyword" placeholder="搜索用户名/邮箱" style="width:260px" clearable @clear="fetchUsers" @keyup.enter="fetchUsers">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button type="primary" @click="fetchUsers">搜索</el-button>
    </div>

    <el-table :data="users" stripe v-loading="loading" style="margin-top:16px">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="username" label="用户名" width="140" />
      <el-table-column prop="email" label="邮箱" min-width="1" />
      <el-table-column label="角色" width="200">
        <template #default="{ row }">
          <el-tag v-for="r in row.roles" :key="r" size="small" style="margin-right:4px">{{ r }}</el-tag>
          <span v-if="!row.roles?.length" style="color:#909399">无</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
            {{ row.is_active ? '正常' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="超管" width="70" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.is_superuser" type="danger" size="small">是</el-tag>
          <span v-else style="color:#909399">-</span>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="注册时间" width="170">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100" align="center" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" text @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div style="margin-top:16px;text-align:right">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="fetchUsers"
        background
      />
    </div>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="dialog.visible" title="编辑用户" width="480px">
      <el-form label-width="80px">
        <el-form-item label="用户名">
          <span>{{ dialog.user?.username }}</span>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="dialog.form.is_active" active-text="正常" inactive-text="禁用" />
        </el-form-item>
        <el-form-item label="超管">
          <el-switch v-model="dialog.form.is_superuser" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="dialog.form.role_codes" multiple placeholder="选择角色" style="width:100%">
            <el-option v-for="r in allRoles" :key="r.code" :label="r.name" :value="r.code" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const loading = ref(false)
const saving = ref(false)
const users = ref([])
const keyword = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const allRoles = ref([])

const dialog = reactive({
  visible: false,
  user: null,
  form: { is_active: true, is_superuser: false, role_codes: [] },
})

function fmtTime(t) {
  if (!t) return '-'
  return String(t).replace('T', ' ').slice(0, 19)
}

async function fetchUsers() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (keyword.value) params.keyword = keyword.value
    const res = await api.get('/users', { params })
    users.value = res.data?.items || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

async function fetchRoles() {
  try {
    const res = await api.get('/users/roles')
    allRoles.value = res.data || []
  } catch { /* ignore */ }
}

function openEdit(user) {
  dialog.user = user
  dialog.form = {
    is_active: user.is_active,
    is_superuser: user.is_superuser,
    role_codes: user.roles || [],
  }
  dialog.visible = true
}

async function handleSave() {
  saving.value = true
  try {
    await api.patch(`/users/${dialog.user.id}`, dialog.form)
    ElMessage.success('已更新')
    dialog.visible = false
    await fetchUsers()
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchUsers()
  fetchRoles()
})
</script>

<style scoped>
.page-header { display: flex; align-items: center; justify-content: space-between; }
</style>
