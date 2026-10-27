<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Delete, View } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'

import { getApiErrorCode, getApiErrorMessage } from '@/api/errors'
import {
  deleteApplicationRecord,
  deleteStageDetail,
  getApplicationRecord,
  getResumeVersionDetail,
  lockApplicationResume,
  saveStageDetail,
  updateApplicationRecord,
} from '@/api/workspace'
import ResumePreview from '@/components/ResumePreview.vue'
import StageDetailForm from '@/components/StageDetailForm.vue'
import { APPLICATION_CHANNELS, CLOSED_REASONS, REJECTED_STAGES } from '@/types/applications'
import type {
  ApplicationRecord,
  ApplicationStageDetail,
  ResumeVersionDetail,
  StageKey,
} from '@/types/workspace'
import {
  eventLabel,
  formatDate,
  formatDateTime,
  statusLabel,
  statusTagType,
  toIsoDate,
} from '@/utils/applicationStatus'

const FIELD_LABELS: Record<string, string> = {
  taken_at: '笔试时间',
  result: '结果',
  rounds: '面试轮次',
  summary: '面试复盘',
  base_city: 'base 地',
  salary: '薪资',
  start_date: '入职时间',
  reply_deadline: '答复截止',
}

const STAGES: StageKey[] = ['written_test', 'interview', 'offer']
// Stable identity: a fresh `{}` on every render would reset the stage form.
const EMPTY_PAYLOAD: Record<string, unknown> = {}

const route = useRoute()
const router = useRouter()

const record = ref<ApplicationRecord | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const savingStage = ref<StageKey | ''>('')
const savingInfo = ref(false)
const changingStatus = ref('')
const lockingVersion = ref(false)
const versionPreviewOpen = ref(false)
const versionDetail = ref<ResumeVersionDetail | null>(null)
const versionLoading = ref(false)

const info = reactive({
  follow_up_at: '',
  channel: '',
  contact_name: '',
  contact_info: '',
  link: '',
  notes: '',
  closed_reason: '',
  rejected_stage: '',
})

const applicationId = computed(() => String(route.params.id))

const detailByStage = computed<Record<string, ApplicationStageDetail>>(() => {
  const map: Record<string, ApplicationStageDetail> = {}
  for (const detail of record.value?.stage_details || []) map[detail.stage] = detail
  return map
})

const missingHint = computed(() => {
  const missing = record.value?.recommended_missing || []
  if (!missing.length) return ''
  return missing.map((field) => FIELD_LABELS[field] || field).join('、')
})

function syncInfo() {
  const current = record.value
  if (!current) return
  info.follow_up_at = current.follow_up_at ? current.follow_up_at.slice(0, 10) : ''
  info.channel = current.channel || ''
  info.contact_name = current.contact_name || ''
  info.contact_info = current.contact_info || ''
  info.link = current.link || ''
  info.notes = current.notes || ''
  info.closed_reason = current.closed_reason || ''
  info.rejected_stage = current.rejected_stage || ''
}

async function load() {
  loading.value = true
  errorMessage.value = ''
  try {
    record.value = await getApplicationRecord(applicationId.value)
    syncInfo()
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
    record.value = null
  } finally {
    loading.value = false
  }
}

async function refresh() {
  record.value = await getApplicationRecord(applicationId.value)
  syncInfo()
}

async function changeStatus(status: string) {
  const current = record.value
  if (!current) return
  changingStatus.value = status
  try {
    record.value = await updateApplicationRecord(current.id, {
      status,
      row_version: current.row_version,
    })
    syncInfo()
    ElMessage.success(`已更新为「${statusLabel(status)}」`)
  } catch (error) {
    if (getApiErrorCode(error) === 'APPLICATION_VERSION_CONFLICT') {
      ElMessage.warning('这条记录已在别处更新，已为你刷新')
      await refresh()
    } else {
      ElMessage.error(getApiErrorMessage(error))
    }
  } finally {
    changingStatus.value = ''
  }
}

async function lockVersion() {
  const current = record.value
  if (!current) return
  lockingVersion.value = true
  try {
    record.value = await lockApplicationResume(current.id, {})
    syncInfo()
    ElMessage.success('已锁定一份简历快照')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    lockingVersion.value = false
  }
}

async function previewVersion() {
  const version = record.value?.resume_version
  if (!version) return
  versionPreviewOpen.value = true
  versionLoading.value = true
  try {
    versionDetail.value = await getResumeVersionDetail(
      version.resume_id,
      version.version_no,
    )
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
    versionPreviewOpen.value = false
  } finally {
    versionLoading.value = false
  }
}

async function saveInfo() {
  const current = record.value
  if (!current) return
  savingInfo.value = true
  try {
    record.value = await updateApplicationRecord(current.id, {
      follow_up_at: toIsoDate(info.follow_up_at),
      channel: info.channel || null,
      contact_name: info.contact_name.trim() || null,
      contact_info: info.contact_info.trim() || null,
      link: info.link.trim() || null,
      notes: info.notes.trim() || null,
      closed_reason: info.closed_reason || null,
      rejected_stage: info.rejected_stage || null,
      row_version: current.row_version,
    })
    syncInfo()
    ElMessage.success('已保存')
  } catch (error) {
    if (getApiErrorCode(error) === 'APPLICATION_VERSION_CONFLICT') {
      ElMessage.warning('这条记录已在别处更新，已为你刷新')
      await refresh()
    } else {
      ElMessage.error(getApiErrorMessage(error))
    }
  } finally {
    savingInfo.value = false
  }
}

async function persistStage(
  stage: StageKey,
  payload: Record<string, unknown>,
  occurredAt: string | null,
) {
  savingStage.value = stage
  try {
    await saveStageDetail(applicationId.value, stage, payload, occurredAt)
    await refresh()
    ElMessage.success('阶段详情已保存')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    savingStage.value = ''
  }
}

async function clearStage(stage: StageKey) {
  const confirmed = await ElMessageBox.confirm('清空后该阶段详情不可恢复，确认继续？', '清空详情', {
    confirmButtonText: '清空',
    cancelButtonText: '取消',
    type: 'warning',
  })
    .then(() => true)
    .catch(() => false)
  if (!confirmed) return
  try {
    await deleteStageDetail(applicationId.value, stage)
    await refresh()
    ElMessage.success('已清空')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

async function removeRecord() {
  const current = record.value
  if (!current) return
  const confirmed = await ElMessageBox.confirm(
    `删除「${current.company_name} · ${current.position_title}」后不可恢复，确认继续？`,
    '删除投递记录',
    { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
  )
    .then(() => true)
    .catch(() => false)
  if (!confirmed) return
  try {
    await deleteApplicationRecord(current.id)
    ElMessage.success('已删除')
    void router.push('/workspace/applications')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

onMounted(load)
</script>

<template>
  <main class="page">
    <RouterLink class="back-link" to="/workspace/applications">
      <el-icon><ArrowLeft /></el-icon>
      返回投递记录
    </RouterLink>

    <el-skeleton v-if="loading" :rows="10" animated />

    <el-alert
      v-else-if="errorMessage"
      :title="errorMessage"
      type="error"
      :closable="false"
      show-icon
    >
      <el-button size="small" @click="load">重新加载</el-button>
    </el-alert>

    <template v-else-if="record">
      <header class="page-head detail-head">
        <div>
          <p class="eyebrow">{{ record.company_name }}</p>
          <h1>{{ record.position_title }}</h1>
          <div class="detail-tags">
            <el-tag :type="statusTagType(record.status)" effect="plain">
              {{ record.status_label }}
            </el-tag>
            <span v-if="record.channel" class="muted-note">{{ record.channel }}</span>
            <span class="muted-note">投递 {{ formatDate(record.applied_at) }}</span>
            <span v-if="record.follow_up_at" class="muted-note">
              跟进 {{ formatDate(record.follow_up_at) }}
            </span>
          </div>
        </div>
        <div class="page-head-actions">
          <RouterLink v-if="record.announcement_id" :to="`/workspace/jobs/${record.announcement_id}`">
            <el-button>查看公告</el-button>
          </RouterLink>
          <el-button type="danger" plain :icon="Delete" @click="removeRecord">删除</el-button>
        </div>
      </header>

      <el-alert
        v-if="missingHint"
        class="detail-hint"
        type="warning"
        :closable="false"
        show-icon
        :title="`建议补充：${missingHint}`"
      >
        详情是补录，不影响状态；补充后回看更完整。
      </el-alert>

      <div class="detail-grid">
        <div class="detail-main">
          <section
            v-for="stage in STAGES"
            :key="stage"
            class="surface stage-card"
          >
            <div class="table-card-head">
              <h2>
                {{ stage === 'written_test' ? '已笔试详情' : stage === 'interview' ? '已面试详情' : '面试通过详情' }}
              </h2>
              <div class="table-card-tools">
                <el-tag v-if="detailByStage[stage]" size="small" type="success" effect="plain">
                  已填写
                </el-tag>
                <span v-else class="muted-note">可留空，随时补录</span>
              </div>
            </div>
            <StageDetailForm
              :stage="stage"
              :payload="detailByStage[stage]?.payload ?? EMPTY_PAYLOAD"
              :occurred-at="detailByStage[stage]?.occurred_at || null"
              :saving="savingStage === stage"
              :removable="Boolean(detailByStage[stage])"
              @save="(payload, occurredAt) => persistStage(stage, payload, occurredAt)"
              @remove="clearStage(stage)"
            />
          </section>

          <section class="surface timeline-card">
            <div class="table-card-head">
              <h2>时间线</h2>
              <span class="muted-note">共 {{ record.events.length }} 条</span>
            </div>
            <el-timeline>
              <el-timeline-item
                v-for="event in [...record.events].reverse()"
                :key="event.id"
                :timestamp="formatDateTime(event.created_at)"
                placement="top"
              >
                <strong>{{ eventLabel(event.event_type) }}</strong>
                <p v-if="event.from_status && event.to_status && event.from_status !== event.to_status">
                  {{ statusLabel(event.from_status) }} → {{ statusLabel(event.to_status) }}
                </p>
                <small v-if="event.note">{{ event.note }}</small>
              </el-timeline-item>
            </el-timeline>
          </section>
        </div>

        <aside class="detail-side">
          <section class="surface side-card">
            <h2>状态流转</h2>
            <p class="muted-note">只能向前推进，可跳级；终态后不再变化。</p>
            <div v-if="record.allowed_transitions.length" class="status-actions">
              <el-button
                v-for="status in record.allowed_transitions"
                :key="status"
                size="small"
                :loading="changingStatus === status"
                @click="changeStatus(status)"
              >
                {{ statusLabel(status) }}
              </el-button>
            </div>
            <p v-else class="muted-note">已是终态，没有可推进的状态。</p>
          </section>

          <section class="surface side-card">
            <h2>投递版本</h2>
            <template v-if="record.resume_version">
              <p class="muted-note">
                本次投递锁定 v{{ record.resume_version.version_no }} ·
                {{ formatDate(record.resume_version.created_at) }}
              </p>
              <p v-if="record.resume_version.note" class="muted-note">
                {{ record.resume_version.note }}
              </p>
              <el-button size="small" :icon="View" @click="previewVersion">查看投递版本</el-button>
            </template>
            <template v-else>
              <p class="muted-note">还没有锁定简历版本；锁定后即使继续改简历，也能回放当时投出的内容。</p>
              <el-button size="small" :loading="lockingVersion" @click="lockVersion">
                锁定当前简历
              </el-button>
            </template>
          </section>

          <section class="surface side-card">
            <h2>跟进与联系方式</h2>
            <el-form label-position="top" @submit.prevent="saveInfo">
              <el-form-item label="跟进日期">
                <el-date-picker v-model="info.follow_up_at" type="date" value-format="YYYY-MM-DD" />
              </el-form-item>
              <el-form-item label="渠道">
                <el-select v-model="info.channel" clearable>
                  <el-option v-for="item in APPLICATION_CHANNELS" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
              <el-form-item label="联系人">
                <el-input v-model="info.contact_name" maxlength="100" />
              </el-form-item>
              <el-form-item label="联系方式">
                <el-input v-model="info.contact_info" maxlength="200" />
              </el-form-item>
              <el-form-item label="公告 / 职位链接">
                <el-input v-model="info.link" maxlength="1000" placeholder="https://" />
              </el-form-item>
              <el-form-item v-if="record.status === 'rejected'" label="已挂原因">
                <el-select v-model="info.closed_reason" clearable>
                  <el-option v-for="item in CLOSED_REASONS" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
              <el-form-item v-if="record.status === 'rejected'" label="挂在哪一环">
                <el-select v-model="info.rejected_stage" clearable>
                  <el-option v-for="item in REJECTED_STAGES" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
              <el-form-item label="备注">
                <el-input v-model="info.notes" type="textarea" :rows="4" maxlength="5000" />
              </el-form-item>
              <el-button type="primary" :loading="savingInfo" @click="saveInfo">保存</el-button>
            </el-form>
          </section>
        </aside>
      </div>

      <el-dialog
        v-model="versionPreviewOpen"
        :title="`投递版本 v${record.resume_version?.version_no ?? ''}`"
        width="820px"
        top="4vh"
      >
        <p class="muted-note">
          这是投递当时锁定的快照，不会随简历后续修改而变化。
        </p>
        <el-skeleton v-if="versionLoading" :rows="8" animated />
        <ResumePreview
          v-else-if="versionDetail"
          :head="versionDetail.head"
          :sections="versionDetail.sections"
          :show-empty="false"
        />
      </el-dialog>
    </template>
  </main>
</template>
