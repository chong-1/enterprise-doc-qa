<template>
  <div class="qa-page">
    <!-- 左侧：知识库选择 + 对话列表 -->
    <div class="qa-sidebar">
      <div style="padding:12px">
        <el-select v-model="selectedKb" placeholder="选择知识库" style="width:100%" @change="onKbChange" clearable>
          <el-option v-for="kb in kbList" :key="kb.id" :label="kb.name" :value="kb.id" />
        </el-select>
      </div>
      <div style="padding:0 12px 12px">
        <el-button style="width:100%" @click="newChat" :disabled="!selectedKb">
          <el-icon><Plus /></el-icon> 新对话
        </el-button>
      </div>
      <div class="conv-list">
        <div
          v-for="c in conversations"
          :key="c.id"
          class="conv-item"
          :class="{ active: c.id === convId }"
          @click="switchConv(c)"
        >
          <div class="conv-title">{{ c.title }}</div>
          <div class="conv-meta">{{ c.message_count }} 条消息 · {{ c.updated_at?.slice(0,10) }}</div>
          <el-button
            class="conv-del"
            size="small"
            type="danger"
            text
            :icon="Delete"
            @click.stop="delConv(c)"
          />
        </div>
      </div>
    </div>

    <!-- 右侧：聊天区 -->
    <div class="qa-main">
      <div class="chat-header" v-if="selectedKb">
        <el-tag type="warning" size="small" style="cursor:pointer" @click="agentMode = !agentMode">
          {{ agentMode ? '🤖 Agent 模式' : '📋 普通模式' }}
        </el-tag>
        <span v-if="convId" style="color:#909399;font-size:13px">对话 #{{ convId }}</span>
      </div>

      <div class="chat-messages" ref="msgContainer">
        <div v-if="messages.length === 0 && selectedKb" class="chat-empty">
          <el-icon :size="48"><ChatDotRound /></el-icon>
          <p>选择知识库，开始提问</p>
        </div>
        <div v-if="!selectedKb" class="chat-empty">
          <el-icon :size="48"><Folder /></el-icon>
          <p>请先选择知识库</p>
        </div>

        <div v-for="(m, i) in messages" :key="i" class="msg-row" :class="m.role">
          <div class="msg-bubble">
            <div class="msg-content" v-text="m.content" />
            <div v-if="m.citations?.length" class="msg-citations">
              <div class="cite-title">📎 引用来源：</div>
              <div v-for="(c, j) in m.citations" :key="j" class="cite-item">
                <span class="cite-doc">{{ c.document }}</span>
                <span class="cite-score">相关度 {{ (c.score * 100).toFixed(0) }}%</span>
                <div class="cite-text">{{ c.text }}</div>
              </div>
            </div>
            <div class="msg-meta">
              {{ m.role === 'user' ? '我' : '助手' }}
              <span v-if="m.processing_time_ms"> · {{ m.processing_time_ms }}ms</span>
            </div>
          </div>
        </div>

        <!-- 流式输出中的临时气泡 -->
        <div v-if="streaming" class="msg-row assistant">
          <div class="msg-bubble">
            <div class="msg-content">{{ streamingText }}<span class="cursor-blink">|</span></div>
          </div>
        </div>
      </div>

      <div class="chat-input">
        <el-input
          v-model="question"
          placeholder="输入问题，按 Enter 发送..."
          :disabled="!selectedKb || streaming"
          @keyup.enter="send"
          size="large"
          clearable
        >
          <template #append>
            <el-button :loading="streaming" :disabled="!question.trim()" @click="send" type="primary">
              <el-icon><Position /></el-icon>
            </el-button>
          </template>
        </el-input>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onMounted } from 'vue'
import { Delete, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const auth = useAuthStore()

// 知识库
const kbList = ref([])
const selectedKb = ref(null)

// 对话
const conversations = ref([])
const convId = ref(null)
const messages = ref([])
const agentMode = ref(false)

// 输入
const question = ref('')
const streaming = ref(false)
const streamingText = ref('')
const msgContainer = ref(null)

onMounted(async () => {
  try {
    const res = await api.get('/knowledge-bases')
    kbList.value = res.data || []
  } catch { /* ignore */ }
  fetchConversations()
})

async function fetchConversations() {
  try {
    const res = await api.get('/conversations', { params: { page_size: 50 } })
    conversations.value = res.data?.items || []
  } catch { /* ignore */ }
}

function onKbChange() {
  convId.value = null
  messages.value = []
}

function newChat() {
  convId.value = null
  messages.value = []
}

async function switchConv(c) {
  convId.value = c.id
  selectedKb.value = c.kb_id
  messages.value = []
  try {
    const res = await api.get(`/conversations/${c.id}/messages`, { params: { page_size: 100 } })
    const msgs = res.data?.items || []
    messages.value = msgs.map(m => ({
      role: m.role,
      content: m.content,
      citations: m.citations || [],
      processing_time_ms: m.processing_time_ms,
    }))
  } catch { /* ignore */ }
  scrollBottom()
}

async function delConv(c) {
  try {
    await ElMessageBox.confirm(`删除对话「${c.title}」？`, '确认', { type: 'warning' })
  } catch { return }
  try {
    await api.delete(`/conversations/${c.id}`)
    ElMessage.success('已删除')
    if (convId.value === c.id) { convId.value = null; messages.value = [] }
    await fetchConversations()
  } catch { /* ignore */ }
}

async function send() {
  const q = question.value.trim()
  if (!q || !selectedKb.value || streaming.value) return
  question.value = ''

  messages.value.push({ role: 'user', content: q })
  scrollBottom()

  streaming.value = true
  streamingText.value = ''

  try {
    const token = auth.token
    const body = JSON.stringify({
      question: q,
      stream: true,
      agent_mode: agentMode.value,
      conversation_id: convId.value,
    })

    const response = await fetch(`/api/v1/qa/${selectedKb.value}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body,
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      ElMessage.error(err.message || '请求失败')
      streaming.value = false
      return
    }

    // SSE 流式解析
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let finalAnswer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data:')) {
          const data = line.slice(5).trim()
          if (!data) continue
          try {
            const json = JSON.parse(data)
            // 检查是否是 done 事件
            if (typeof json === 'string' && line.includes('"event":"done"')) {
              // done event handled below
            }
          } catch {
            // token 是纯文本，直接追加
            streamingText.value += data
            finalAnswer += data
          }
        }
        // SSE event lines
        if (line.startsWith('event: done')) {
          // 下一个 data 就是完整答案
        }
      }
    }
    // 处理最后一段 buffer
    if (buffer.startsWith('data:')) {
      const data = buffer.slice(5).trim()
      if (data && data !== '[DONE]') {
        try { JSON.parse(data) } catch {
          streamingText.value += data
          finalAnswer += data
        }
      }
    }

    const answer = finalAnswer || streamingText.value
    messages.value.push({
      role: 'assistant',
      content: answer,
      citations: [],
      processing_time_ms: 0,
    })
    streamingText.value = ''

    // 如果首次问答，获取新建的 conversation_id
    if (!convId.value) {
      await fetchConversations()
      // 取最新对话的 ID
      if (conversations.value.length > 0) {
        convId.value = conversations.value[0].id
        // 取消息列表里的引用
        try {
          const msgRes = await api.get(`/conversations/${convId.value}/messages`, { params: { page_size: 2 } })
          const items = msgRes.data?.items || []
          const lastMsg = items.find(m => m.role === 'assistant')
          if (lastMsg?.citations?.length) {
            const ourMsg = messages.value[messages.value.length - 1]
            ourMsg.citations = lastMsg.citations
            ourMsg.processing_time_ms = lastMsg.processing_time_ms
          }
        } catch { /* ignore */ }
      }
    }

    scrollBottom()
  } catch (e) {
    ElMessage.error('请求失败: ' + (e.message || '网络错误'))
  } finally {
    streaming.value = false
  }
}

function scrollBottom() {
  nextTick(() => {
    const el = msgContainer.value
    if (el) el.scrollTop = el.scrollHeight
  })
}
</script>

<style scoped>
.qa-page { display: flex; height: calc(100vh - 60px - 48px); margin: -24px; }
.qa-sidebar { width: 280px; background: #fff; border-right: 1px solid #e6e6e6; display: flex; flex-direction: column; }
.conv-list { flex: 1; overflow-y: auto; }
.conv-item { padding: 12px; border-bottom: 1px solid #f0f0f0; cursor: pointer; position: relative; }
.conv-item:hover, .conv-item.active { background: #e6f7ff; }
.conv-title { font-size: 14px; font-weight: 500; color: #303133; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding-right: 24px; }
.conv-meta { font-size: 12px; color: #909399; margin-top: 4px; }
.conv-del { position: absolute; top: 8px; right: 8px; }
.qa-main { flex: 1; display: flex; flex-direction: column; background: #f5f5f5; }
.chat-header { padding: 10px 16px; background: #fff; border-bottom: 1px solid #e6e6e6; display: flex; align-items: center; justify-content: space-between; }
.chat-messages { flex: 1; overflow-y: auto; padding: 16px; }
.chat-empty { text-align: center; padding: 80px 0; color: #909399; }
.msg-row { margin-bottom: 16px; display: flex; }
.msg-row.user { justify-content: flex-end; }
.msg-row.assistant { justify-content: flex-start; }
.msg-bubble { max-width: 75%; padding: 12px 16px; border-radius: 12px; line-height: 1.7; }
.msg-row.user .msg-bubble { background: #409EFF; color: #fff; border-bottom-right-radius: 4px; }
.msg-row.assistant .msg-bubble { background: #fff; color: #303133; border-bottom-left-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
.msg-content { white-space: pre-wrap; word-break: break-word; }
.msg-meta { font-size: 11px; margin-top: 6px; opacity: 0.7; }
.msg-citations { margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(0,0,0,.08); font-size: 13px; }
.cite-title { font-weight: 600; margin-bottom: 6px; color: #606266; }
.cite-item { margin-bottom: 8px; }
.cite-doc { color: #409EFF; font-weight: 500; }
.cite-score { color: #909399; margin-left: 8px; font-size: 11px; }
.cite-text { background: #f5f5f5; padding: 6px 8px; border-radius: 4px; margin-top: 4px; font-size: 12px; color: #606266; max-height: 60px; overflow: hidden; }
.chat-input { padding: 12px 16px; background: #fff; border-top: 1px solid #e6e6e6; }
.cursor-blink { animation: blink 0.6s infinite; color: #409EFF; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
</style>
