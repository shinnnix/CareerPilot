<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatDotRound, Refresh } from '@element-plus/icons-vue'

import { confirmAgentRun, createAgentRun, resumeAgentRun, subscribeAgentEvents } from '@/api/agent'
import { listApplications } from '@/api/applications'
import { listDocuments } from '@/api/documents'
import { getApiErrorMessage } from '@/api/errors'
import { listJobs } from '@/api/jobs'
import type { AgentEventItem, AgentIntent, AgentRun, AgentRunInput } from '@/types/agent'
import type { ApplicationStatus, ApplicationSummary } from '@/types/applications'
import type { DocumentSummary } from '@/types/documents'
import type { Job } from '@/types/jobs'
import AgentConfirmationCard from '@/components/AgentConfirmationCard.vue'

const form = reactive<AgentRunInput>({
  message: '帮我找适合的 RAG 实习职位',
  intent: 'job_search',
  query: 'RAG',
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
  intent_routed: '完成意图路由',
  tool_planned: '完成工具规划',
  tool_started: '开始执行工具',
  confirmation_required: '等待人工确认',
  confirmation_rejected: '用户拒绝操作',
  checkpoint_recovered: '从持久化检查点恢复',
  run_completed: '任务完成',
  run_failed: '任务失败',
  stream_end: '事件流结束',
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
    job_search: '帮我找适合的 RAG 实习职位',
    match_report: '分析这份简历与职位是否匹配',
    skill_gap: '我还缺哪些技能',
    create_application: '把这个职位加入申请看板',
    update_application: '更新这条申请的状态',
  }
  form.message = prompts[intent]
}

onMounted(loadOptions)
onBeforeUnmount(() => eventSource?.close())
</script>

<template>
  <main class="page">
    <section class="agent-hero">
      <div>
        <p class="eyebrow">LANGGRAPH WORKFLOW</p>
        <h1>每一步都能暂停、确认和恢复</h1>
        <p>只读工具自动执行；修改申请数据前必须人工确认，并使用幂等 Key 防止重复写入。</p>
      </div>
    </section>

    <div class="agent-layout">
      <section class="surface agent-console">
        <el-form label-position="top">
          <el-form-item label="任务类型">
            <el-select v-model="form.intent" @change="changeIntent">
              <el-option label="搜索职位" value="job_search" />
              <el-option label="匹配报告" value="match_report" />
              <el-option label="技能差距" value="skill_gap" />
              <el-option label="创建申请" value="create_application" />
              <el-option label="更新申请" value="update_application" />
            </el-select>
          </el-form-item>
          <el-form-item label="告诉 Agent 你的目标">
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
                <el-option v-for="status in (['preparing','applied','interview','offer','rejected','withdrawn'] as ApplicationStatus[])" :key="status" :label="status" :value="status" />
              </el-select>
            </el-form-item>
          </template>
          <el-button type="primary" :icon="ChatDotRound" :loading="loading" @click="startRun">
            启动工作流
          </el-button>
        </el-form>
      </section>

      <section class="surface agent-trace">
        <div class="section-heading section-heading--compact">
          <div><p class="eyebrow">DURABLE TRACE</p><h2>执行轨迹</h2></div>
          <el-tag v-if="run" :type="run.status === 'completed' ? 'success' : run.status === 'failed' ? 'danger' : 'warning'">{{ run.status }}</el-tag>
        </div>
        <el-empty v-if="!run" description="启动任务后，这里会显示节点事件" />
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
