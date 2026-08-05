<template>
  <div class="qa-page">
    <!-- ====== 左侧面板 ====== -->
    <aside class="qa-sidebar">
      <div class="sb-header">
        <el-select
          v-model="selectedKb"
          placeholder="选择知识库"
          style="width:100%"
          @change="onKbChange"
          clearable
          size="large"
        >
          <el-option
            v-for="kb in kbList"
            :key="kb.id"
            :label="kb.name"
            :value="kb.id"
          >
            <div class="kb-opt">
              <span>{{ kb.name }}</span>
              <span class="kb-opt-meta">📄{{ kb.document_count }} · {{ kb.my_role }}</span>
            </div>
          </el-option>
        </el-select>
      </div>

      <div class="sb-new-btn">
        <el-button style="width:100%" @click="newChat" :disabled="!selectedKb" size="large">
          <el-icon><Plus /></el-icon> 新对话
        </el-button>
      </div>

      <div class="conv-list" v-if="conversations.length">
        <div
          v-for="c in conversations"
          :key="c.id"
          class="conv-item"
          :class="{ active: c.id === convId }"
          @click="switchConv(c)"
        >
          <div class="conv-head">
            <span class="conv-title" :title="c.title">{{ c.title }}</span>
            <span class="conv-time">{{ dateShort(c.updated_at) }}</span>
          </div>
          <div class="conv-foot">
            <span>{{ c.message_count }} 条消息</span>
            <el-popconfirm
              title="删除此对话？"
              @confirm="delConv(c)"
              @click.stop
              width="180"
            >
              <template #reference>
                <el-button class="conv-del-btn" size="small" text type="danger" :icon="Delete" @click.stop />
              </template>
            </el-popconfirm>
          </div>
        </div>
      </div>
      <div v-else-if="selectedKb" class="conv-empty">
        <p>暂无对话</p>
        <p style="font-size:12px;color:#c0c4cc">选择知识库后开始提问</p>
      </div>
    </aside>

    <!-- ====== 右侧聊天区 ====== -->
    <main class="qa-main">
      <!-- 顶栏 -->
      <header class="chat-topbar" v-if="selectedKb">
        <div class="topbar-left">
          <span class="kb-badge">{{ currentKbName }}</span>
          <el-tooltip content="Agent 模式会先用 LLM 分析意图，再决定走直接问答还是多步推理" placement="bottom">
            <el-tag
              :type="agentMode ? 'danger' : 'info'"
              size="small"
              class="agent-toggle"
              @click="agentMode = !agentMode"
            >
              {{ agentMode ? '🤖 Agent 推理' : '📋 直接问答' }}
            </el-tag>
          </el-tooltip>
        </div>
        <div class="topbar-right">
          <span v-if="convId" style="font-size:13px;color:#909399">#{{ convId }}</span>
        </div>
      </header>

      <!-- 消息区域 -->
      <div class="chat-messages" ref="msgContainer" @scroll="onScroll">
        <div v-if="!selectedKb" class="msg-empty">
          <div class="empty-icon">💬</div>
          <h3>企业文档智能问答</h3>
          <p>选择一个知识库，输入问题开始对话</p>
          <div class="empty-tips">
            <div class="tip-item">🔍 支持混合检索（语义 + 关键词）</div>
            <div class="tip-item">📎 回答附带文档引用来源</div>
            <div class="tip-item">🤖 可切换 Agent 模式进行复杂推理</div>
          </div>
        </div>

        <div v-if="selectedKb && messages.length === 0 && !streaming" class="msg-empty">
          <div class="empty-icon">✨</div>
          <p>开始你的第一个问题吧</p>
        </div>

        <template v-for="(m, i) in messages" :key="i">
          <!-- 用户消息 -->
          <div v-if="m.role === 'user'" class="msg-row user">
            <div class="msg-wrapper">
              <div class="msg-bubble user-bubble">{{ m.content }}</div>
            </div>
            <div class="msg-avatar user-avatar">{{ auth.user?.username?.[0]?.toUpperCase() || 'U' }}</div>
          </div>

          <!-- 助手消息 -->
          <div v-else class="msg-row assistant">
            <div class="msg-avatar bot-avatar">🤖</div>
            <div class="msg-wrapper">
              <div class="msg-bubble bot-bubble">
                <div class="msg-text" v-text="m.content" />
                <!-- 引用 -->
                <div v-if="m.citations?.length" class="cite-block">
                  <div class="cite-header" @click="m._citeOpen = !m._citeOpen">
                    📎 {{ m.citations.length }} 条引用来源
                    <el-icon style="margin-left:4px"><ArrowDown v-if="!m._citeOpen" /><ArrowUp v-else /></el-icon>
                  </div>
                  <div v-show="m._citeOpen !== false" class="cite-list">
                    <div v-for="(c, j) in m.citations" :key="j" class="cite-card">
                      <div class="cite-card-head">
                        <span class="cite-doc">{{ c.document }}</span>
                        <el-progress
                          :percentage="Math.round(c.score * 100)"
                          :stroke-width="4"
                          :show-text="false"
                          style="width:60px"
                          :color="scoreColor(c.score)"
                        />
                        <span class="cite-pct">{{ Math.round(c.score * 100) }}%</span>
                      </div>
                      <div class="cite-text">{{ c.text }}</div>
                    </div>
                  </div>
                </div>
              </div>
              <div class="msg-actions">
                <span class="msg-time">{{ m._time || '' }}</span>
                <el-button size="small" text @click="copyText(m.content)">
                  <el-icon><CopyDocument /></el-icon>
                </el-button>
              </div>
            </div>
          </div>
        </template>

        <!-- 流式输出中 -->
        <div v-if="streaming" class="msg-row assistant">
          <div class="msg-avatar bot-avatar">🤖</div>
          <div class="msg-wrapper">
            <div class="msg-bubble bot-bubble">
              <div class="msg-text">
                {{ streamingText }}
                <span class="typing-cursor">▊</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 自动滚底锚点 -->
        <div ref="msgBottom" />
      </div>

      <!-- 输入区 -->
      <div class="chat-input-bar" v-if="selectedKb">
        <el-input
          v-model="question"
          placeholder="输入问题，Enter 发送，Shift+Enter 换行"
          :disabled="streaming"
          :rows="1"
          type="textarea"
          resize="none"
          class="input-area"
          @keydown.enter.exact.prevent="send"
          @keydown.shift.enter.prevent="question += '\n'"
        />
        <el-button
          type="primary"
          :loading="streaming"
          :disabled="!question.trim()"
          @click="send"
          class="send-btn"
        >
          <el-icon :size="18"><Position /></el-icon>
        </el-button>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
import { Delete, Plus, CopyDocument, ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const auth = useAuthStore()

// ====== 知识库 ======
const kbList = ref([])
const selectedKb = ref(null)

const currentKbName = computed(() => {
  const kb = kbList.value.find(k => k.id === selectedKb.value)
  return kb ? `📚 ${kb.name}` : ''
})

// ====== 对话 ======
const conversations = ref([])
const convId = ref(null)
const messages = ref([])
const agentMode = ref(false)
const msgContainer = ref(null)
const msgBottom = ref(null)
const userScrolledUp = ref(false)

// ====== 输入 ======
const question = ref('')
const streaming = ref(false)
const streamingText = ref('')

// ====== 时间 ======
const now = () => {
  const d = new Date()
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const dateShort = (t) => {
  if (!t) return ''
  return String(t).slice(0, 10)
}

const scoreColor = (s) => {
  if (s > 0.7) return '#67c23a'
  if (s > 0.4) return '#e6a23c'
  return '#f56c6c'
}

// ====== 初始化 ======
onMounted(async () => {
  try {
    const res = await api.get('/knowledge-bases')
    kbList.value = res.data || []
  } catch {}
  await fetchConversations()
})

// ====== 对话列表 ======
async function fetchConversations() {
  try {
    const res = await api.get('/conversations', { params: { page_size: 50 } })
    conversations.value = res.data?.items || []
  } catch {}
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
      _time: m.created_at ? String(m.created_at).slice(11, 19) : '',
    }))
  } catch {}
  await nextTick()
  scrollToBottom(true)
}

async function delConv(c) {
  try {
    await api.delete(`/conversations/${c.id}`)
    ElMessage.success('已删除')
    if (convId.value === c.id) { convId.value = null; messages.value = [] }
    await fetchConversations()
  } catch {}
}

// ====== 发送消息 ======
async function send() {
  const q = question.value.trim()
  if (!q || !selectedKb.value || streaming.value) return
  question.value = ''

  messages.value.push({ role: 'user', content: q, _time: now() })
  await nextTick()
  scrollToBottom(true)

  streaming.value = true
  streamingText.value = ''

  try {
    const response = await fetch(`/api/v1/qa/${selectedKb.value}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${auth.token}`,
      },
      body: JSON.stringify({
        question: q,
        stream: true,
        agent_mode: agentMode.value,
        conversation_id: convId.value,
      }),
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      ElMessage.error(err.message || '问答请求失败')
      streaming.value = false
      return
    }

    const contentType = response.headers.get('content-type') || ''

    // ===== 非流式响应（Agent 模式后端返回普通 JSON，不是 SSE）=====
    if (!contentType.includes('text/event-stream')) {
      const data = await response.json()
      const body = data?.data || {}
      const answer = body.answer || ''
      messages.value.push({
        role: 'assistant',
        content: answer,
        citations: body.citations || [],
        _time: now(),
        processing_time_ms: body.processing_time_ms || 0,
      })
      if (body.conversation_id) convId.value = body.conversation_id
      await fetchConversations()
      streamingText.value = ''
      scrollToBottom(true)
      return
    }

    // ===== SSE 流式响应（普通 RAG 模式）=====
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let finalAnswer = ''
    let currentEvent = ''  // 跟踪当前 event 类型，done 事件的 data 是完整答案，须跳过避免重复

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('event:')) {
          currentEvent = line.slice(6).trim()
          continue
        }
        if (line.startsWith('data:')) {
          const data = line.slice(5).trim()
          if (!data || data === '[DONE]') continue
          if (currentEvent === 'done') continue  // done 的 data = 完整答案，token 流已累积过
          // 尝试解析 JSON（事件对象），失败则当纯文本 token
          try {
            const json = JSON.parse(data)
            if (json.event === 'done') continue
            if (typeof json === 'string') {
              streamingText.value += json
              finalAnswer += json
            }
          } catch {
            streamingText.value += data
            finalAnswer += data
          }
          await nextTick()
          scrollToBottom(false)
        }
      }
    }
    // 处理最后 buffer
    if (buffer.startsWith('data:') && buffer.slice(5).trim()) {
      const data = buffer.slice(5).trim()
      if (data !== '[DONE]' && currentEvent !== 'done') {
        streamingText.value += data
        finalAnswer += data
      }
    }

    const answer = finalAnswer || streamingText.value
    messages.value.push({
      role: 'assistant',
      content: answer,
      citations: [],
      _time: now(),
      processing_time_ms: 0,
    })
    streamingText.value = ''

    // 首次：刷新对话列表 + 拿引用
    if (!convId.value) {
      await fetchConversations()
      if (conversations.value.length > 0) {
        convId.value = conversations.value[0].id
        try {
          const msgRes = await api.get(`/conversations/${convId.value}/messages`, { params: { page_size: 2 } })
          const items = msgRes.data?.items || []
          const lastMsg = items.find(m => m.role === 'assistant')
          if (lastMsg?.citations?.length) {
            const ourMsg = messages.value[messages.value.length - 1]
            ourMsg.citations = lastMsg.citations
            ourMsg.processing_time_ms = lastMsg.processing_time_ms
          }
        } catch {}
      }
    }

    scrollToBottom(true)
  } catch (e) {
    ElMessage.error('网络错误: ' + (e.message || ''))
  } finally {
    streaming.value = false
  }
}

// ====== 滚动 ======
function onScroll() {
  const el = msgContainer.value
  if (!el) return
  userScrolledUp.value = el.scrollHeight - el.scrollTop - el.clientHeight > 80
}

function scrollToBottom(force) {
  if (!force && userScrolledUp.value) return
  nextTick(() => {
    msgBottom.value?.scrollIntoView({ behavior: 'smooth' })
  })
}

// ====== 工具 ======
async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选择')
  }
}
</script>

<style scoped>
/* ====== 整体布局 ====== */
.qa-page {
  display: flex;
  height: calc(100vh - 60px - 48px);
  margin: -24px;
  background: #f5f7fa;
}

/* ====== 侧边栏 ====== */
.qa-sidebar {
  width: 280px;
  background: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.sb-header { padding: 16px 16px 0; }
.sb-new-btn { padding: 12px 16px; }
.kb-opt { display: flex; justify-content: space-between; align-items: center; width: 100%; }
.kb-opt-meta { font-size: 12px; color: #909399; }

/* 对话列表 */
.conv-list { flex: 1; overflow-y: auto; padding: 0 8px 8px; }
.conv-item {
  padding: 12px;
  margin-bottom: 4px;
  border-radius: 8px;
  cursor: pointer;
  transition: background .2s;
}
.conv-item:hover { background: #f0f5ff; }
.conv-item.active { background: #e6f0ff; }
.conv-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.conv-title { font-size: 14px; font-weight: 500; color: #303133; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 170px; }
.conv-time { font-size: 11px; color: #c0c4cc; flex-shrink: 0; }
.conv-foot { display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: #909399; }
.conv-del-btn { padding: 2px; }
.conv-empty { text-align: center; padding: 40px 20px; color: #909399; }

/* ====== 主聊天区 ====== */
.qa-main { flex: 1; display: flex; flex-direction: column; min-width: 0; }

/* 顶栏 */
.chat-topbar {
  height: 52px;
  padding: 0 20px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}
.topbar-left { display: flex; align-items: center; gap: 12px; }
.kb-badge { font-size: 14px; font-weight: 600; color: #303133; }
.agent-toggle { cursor: pointer; user-select: none; }

/* 消息区 */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  scroll-behavior: smooth;
}
.msg-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;
}
.empty-icon { font-size: 56px; margin-bottom: 16px; }
.msg-empty h3 { margin: 0 0 8px; color: #303133; font-size: 20px; }
.msg-empty p { margin: 0 0 24px; }
.empty-tips { display: flex; flex-direction: column; gap: 8px; }
.tip-item {
  padding: 8px 16px;
  background: #fff;
  border-radius: 8px;
  font-size: 13px;
  color: #606266;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
}

/* 消息行 */
.msg-row { display: flex; margin-bottom: 20px; gap: 10px; }
.msg-row.user { justify-content: flex-end; }
.msg-row.assistant { justify-content: flex-start; }

.msg-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
}
.user-avatar { background: #409EFF; color: #fff; }
.bot-avatar { background: #f0f2f5; font-size: 18px; }

.msg-wrapper { max-width: 72%; display: flex; flex-direction: column; }

.msg-bubble { padding: 12px 16px; border-radius: 12px; line-height: 1.65; word-break: break-word; }
.user-bubble { background: #409EFF; color: #fff; border-bottom-right-radius: 4px; }
.bot-bubble { background: #fff; color: #303133; border-bottom-left-radius: 4px; box-shadow: 0 1px 4px rgba(0,0,0,.06); }

.msg-text { white-space: pre-wrap; }

/* 引用 */
.cite-block { margin-top: 12px; padding-top: 10px; border-top: 1px solid #ebeef5; font-size: 13px; }
.cite-header { font-weight: 600; color: #606266; cursor: pointer; display: flex; align-items: center; user-select: none; }
.cite-list { margin-top: 8px; display: flex; flex-direction: column; gap: 8px; }
.cite-card { background: #fafafa; border-radius: 8px; padding: 10px 12px; border: 1px solid #f0f0f0; }
.cite-card-head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.cite-doc { font-size: 12px; color: #409EFF; font-weight: 500; }
.cite-pct { font-size: 11px; color: #909399; }
.cite-text { font-size: 12px; color: #606266; line-height: 1.5; max-height: 48px; overflow: hidden; }

/* 消息操作 */
.msg-actions { display: flex; align-items: center; gap: 4px; margin-top: 4px; padding-left: 4px; }
.msg-time { font-size: 11px; color: #c0c4cc; }

/* 流式光标 */
.typing-cursor {
  display: inline;
  animation: blink 0.8s infinite;
  color: #409EFF;
  font-weight: bold;
}
@keyframes blink { 0%, 100% { opacity: 1 } 50% { opacity: 0 } }

/* 输入区 */
.chat-input-bar {
  padding: 12px 20px 16px;
  background: #fff;
  border-top: 1px solid #e4e7ed;
  display: flex;
  align-items: flex-end;
  gap: 10px;
  flex-shrink: 0;
}
.input-area { flex: 1; }
.send-btn {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
