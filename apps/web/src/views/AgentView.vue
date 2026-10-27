<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatDotRound, Refresh } from '@element-plus/icons-vue'

import { confirmAgentRun, createAgentRun, resumeAgentRun, subscribeAgentEvents } from '@/api/agent'
import { listApplications } from '@/api/applications'
import { listDocuments } from '@/api/documents'
import { getApiErrorMessage } from '@/api/errors'
import { listJobs } from '@/api/jobs'
import { sendAssistantMessage } from '@/api/settings'
import type { ChatMessage } from '@/api/settings'
import { useAiConfigStore } from '@/stores/ai-config'
import type { AgentEventItem, AgentIntent, AgentRun, AgentRunInput } from '@/types/agent'
import type { ApplicationStatus, ApplicationSummary } from '@/types/applications'
import { APPLICATION_STATUS_LABELS } from '@/types/applications'
import type { DocumentSummary } from '@/types/documents'
import type { Job } from '@/types/jobs'
import AgentConfirmationCard from '@/components/AgentConfirmationCard.vue'

const aiStore = useAiConfigStore()
const chatInput = ref('')
const chatHistory = ref<ChatMessage[]>([])
const chatting = ref(false)
const chatError = ref('')

/** Plan §5.3.5: chat must not silently degrade into a fake answer. */
const chatBlocked = computed(() => !aiStore.hasChat)

const form = reactive<AgentRunInput>({
  message: '帮我找适合的实习职位',
  intent: 'job_search',
  query: '',
  max_steps: 8,
})
const jobs = ref<Job[]>([])
const resumes = ref<DocumentSummary[]>([])
const applications = ref<ApplicationSummary[]>([])
const run = ref<AgentRun | null>(null)
const events = ref<AgentEventItem[]>([])
const loading = ref(false)
const confirmationKey = ref('')
let eventSource: EventSource | null = null

const needsJob = computed(() => ['match_report', 'skill_gap', 'create_application'].includes(form.intent || ''))
const needsResume = computed(() => ['match_report', 'skill_gap'].includes(form.intent || ''))
const needsApplication = computed(() => form.intent === 'update_application')

const eventLabels: Record<string, string> = {
  run_started: '任务已创建',
  intent_routed: '理解目标',
  tool_planned: '安排步骤',
  tool_started: '执行中',
  confirmation_required: '等待你确认',
  confirmation_rejected: '已取消该操作',
  checkpoint_recovered: '从中断处恢复',
  run_completed: '完成',
  run_failed: '失败',
  stream_end: '结束',
}

async function loadOptions() {
  try {
    const [jobResponse, resumeResponse, applicationResponse] = await Promise.all([
      listJobs({ page: 1, page_size: 100 }),
      listDocuments({ document_type: 'resume', page_size: 100 }),
      listApplications(),
    ])
    jobs.value = jobResponse.items
    resumes.value = resumeResponse.items
    applications.value = applicationResponse.items
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

function watchEvents(runId: string) {
  eventSource?.close()
  eventSource = subscribeAgentEvents(runId, (event) => {
    if (event.event !== 'stream_end') events.value.push(event)
  })
}

async function startRun() {
  loading.value = true
  events.value = []
  try {
    run.value = await createAgentRun(form)
    confirmationKey.value = `agent-${run.value.id}-${crypto.randomUUID()}`
    watchEvents(run.value.id)
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function confirm(approved: boolean) {
  if (!run.value) return
  loading.value = true
  try {
    run.value = await confirmAgentRun(run.value.id, approved, confirmationKey.value)
    watchEvents(run.value.id)
    await loadOptions()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function resume() {
  if (!run.value) return
  loading.value = true
  try {
    run.value = await resumeAgentRun(run.value.id)
    watchEvents(run.value.id)
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function changeIntent(intent: AgentIntent) {
  const prompts: Record<AgentIntent, string> = {
    job_search: '帮我找适合的实习职位',
    match_report: '分析这份简历与职位是否匹配',
    skill_gap: '我还缺哪些技能',
    create_application: '把这个职位加入投递记录',
    update_application: '更新这条投递的状态',
  }
  form.message = prompts[intent]
}

async function sendChat() {
  const text = chatInput.value.trim()
  if (!text || chatting.value) return
  chatHistory.value.push({ role: 'user', content: text })
  chatInput.value = ''
  chatting.value = true
  chatError.value = ''
  try {
    const reply = await sendAssistantMessage(
      text,
      chatHistory.value.slice(0, -1),
      aiStore.configFor('chat'),
    )
    chatHistory.value.push({ role: 'assistant', content: reply.reply })
  } catch (error) {
    chatError.value = getApiErrorMessage(error)
  } finally {
    chatting.value = false
  }
}

onMounted(() => {
  aiStore.reload()
  void loadOptions()
})
onBeforeUnmount(() => eventSource?.close())
</script>

<template>
  <main class="page">
    <header class="page-head">
      <div>
        <p class="eyebrow">更多工具</p>
        <h1>求职助手</h1>
        <p class="page-desc">
          能动手的助手：筛职位、解释匹配、生成材料、创建投递、更新状态。
          只读动作直接执行；会改数据的动作先展示参数，等你确认后再幂等写入。
        </p>
      </div>
      <div class="page-head-actions">
        <RouterLink to="/workspace/settings">
          <el-button>{{ aiStore.hasChat ? '管理对话模型' : '去绑定对话模型' }}</el-button>
        </RouterLink>
      </div>
    </header>

    <section class="surface agent-chat">
      <div class="table-card-head">
        <h2>直接对话</h2>
        <el-tag size="small" effect="plain" :type="aiStore.hasChat ? 'success' : 'warning'">
          {{ aiStore.hasChat ? `已绑定 · ${aiStore.configFor('chat')?.model}` : '未绑定对话模型' }}
        </el-tag>
      </div>

      <el-alert
        v-if="chatBlocked"
        class="agent-chat-alert"
        type="warning"
        :closable="false"
        show-icon
        title="还没有配置对话模型"
      >
        助手不会在缺少凭据时编造答案。请到「AI 与设置」绑定 chat 任务后再对话；
        下面的工作流（筛职位、建投递）不依赖模型，现在就能用。
        <RouterLink class="inline-link" to="/workspace/settings">去配置</RouterLink>
      </el-alert>

      <div v-if="chatHistory.length" class="agent-chat-log">
        <div
          v-for="(item, index) in chatHistory"
          :key="index"
          class="agent-chat-line"
          :class="`agent-chat-line--${item.role}`"
        >
          <p>{{ item.content }}</p>
        </div>
      </div>

      <div class="agent-chat-input">
        <el-input
          v-model="chatInput"
          type="textarea"
          :rows="2"
          :disabled="chatBlocked"
          placeholder="例如：这周该优先跟进哪几条投递？"
          @keydown.enter.exact.prevent="sendChat"
        />
        <el-button
          type="primary"
          :loading="chatting"
          :disabled="chatBlocked || !chatInput.trim()"
          @click="sendChat"
        >
          发送
        </el-button>
      </div>
      <p v-if="chatError" class="muted-note agent-chat-error">{{ chatError }}</p>
    </section>

    <div class="agent-layout">
      <section class="surface agent-console">
        <div class="section-heading section-heading--compact">
          <div>
            <p class="eyebrow">按目标执行</p>
            <h2>选一个任务</h2>
          </div>
        </div>
        <el-form label-position="top">
          <el-form-item label="任务类型">
            <el-select v-model="form.intent" @change="changeIntent">
              <el-option label="搜索职位" value="job_search" />
              <el-option label="匹配报告" value="match_report" />
              <el-option label="技能差距" value="skill_gap" />
              <el-option label="创建投递" value="create_application" />
              <el-option label="更新投递" value="update_application" />
            </el-select>
          </el-form-item>
          <el-form-item label="告诉助手你的目标">
            <el-input v-model="form.message" type="textarea" :rows="3" />
          </el-form-item>
          <div v-if="form.intent === 'job_search'" class="form-grid">
            <el-form-item label="关键词"><el-input v-model="form.query" /></el-form-item>
            <el-form-item label="城市"><el-input v-model="form.city" clearable /></el-form-item>
          </div>
          <el-form-item v-if="needsJob" label="职位">
            <el-select v-model="form.job_id" filterable>
              <el-option v-for="job in jobs" :key="job.id" :label="`${job.company_name} · ${job.title}`" :value="job.id" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="needsResume" label="简历">
            <el-select v-model="form.resume_document_id">
              <el-option v-for="resume in resumes" :key="resume.id" :label="resume.display_name" :value="resume.id" />
            </el-select>
          </el-form-item>
          <template v-if="needsApplication">
            <el-form-item label="申请记录">
              <el-select v-model="form.application_id">
                <el-option v-for="item in applications" :key="item.id" :label="`${item.company_name} · ${item.job_title}`" :value="item.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="目标状态">
              <el-select v-model="form.application_status">
                <el-option v-for="status in (['not_applied','applied','written_test','interview_done','offer','rejected','withdrawn'] as ApplicationStatus[])" :key="status" :label="APPLICATION_STATUS_LABELS[status]" :value="status" />
              </el-select>
            </el-form-item>
          </template>
          <el-button type="primary" :icon="ChatDotRound" :loading="loading" @click="startRun">
            开始
          </el-button>
        </el-form>
      </section>

      <section class="surface agent-trace">
        <div class="section-heading section-heading--compact">
          <div><p class="eyebrow">执行记录</p><h2>做了什么</h2></div>
          <el-tag v-if="run" :type="run.status === 'completed' ? 'success' : run.status === 'failed' ? 'danger' : 'warning'">{{ run.status }}</el-tag>
        </div>
        <el-empty v-if="!run" description="开始任务后，这里会显示每一步发生了什么" />
        <template v-else>
          <el-timeline>
            <el-timeline-item v-for="event in events" :key="`${event.id}-${event.event}`" :type="event.event === 'run_failed' ? 'danger' : event.event === 'run_completed' ? 'success' : 'primary'">
              <strong>{{ eventLabels[event.event] || event.event }}</strong>
              <pre>{{ JSON.stringify(event.data, null, 2) }}</pre>
            </el-timeline-item>
          </el-timeline>
          <AgentConfirmationCard
            v-if="run.status === 'waiting_confirmation'"
            :tool-name="String(run.pending_action?.tool || '')"
            :loading="loading"
            @approve="confirm(true)"
            @reject="confirm(false)"
          />
          <el-button v-if="run.status === 'failed'" :icon="Refresh" @click="resume">从检查点恢复</el-button>
          <div v-if="run.result" class="agent-result">
            <h3>最终结果</h3>
            <pre>{{ JSON.stringify(run.result, null, 2) }}</pre>
          </div>
        </template>
      </section>
    </div>
  </main>
</template>
