<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, DocumentAdd, Link } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'

import { getApiErrorMessage } from '@/api/errors'
import { listResumes } from '@/api/resumes'
import { getJobAnnouncement, markJob } from '@/api/workspace'
import ApplicationFormDialog from '@/components/ApplicationFormDialog.vue'
import type { ResumeSummary } from '@/types/resumes'
import type { JobAnnouncement, JobPositionItem } from '@/types/workspace'

const route = useRoute()
const router = useRouter()

const announcement = ref<JobAnnouncement | null>(null)
const loading = ref(true)
const errorMessage = ref('')
const applicationOpen = ref(false)
const presets = ref<string[]>([])
const resumes = ref<ResumeSummary[]>([])
const resumePickerOpen = ref(false)
const selectedResumeId = ref('')

const announcementId = computed(() => String(route.params.id))

function statusTagType(status: string | undefined): 'success' | 'warning' | 'info' | 'danger' | 'primary' {
  if (status === 'offer') return 'success'
  if (status === 'rejected') return 'danger'
  if (status === 'written_test' || status === 'interview_done' || status === 'interview') {
    return 'warning'
  }
  if (status === 'applied') return 'primary'
  return 'info'
}

const rowStatusType = computed(() => statusTagType(announcement.value?.mark_status))

/** Every position of this announcement already has an application row. */
const allPositionsApplied = computed(() => {
  const positions = announcement.value?.positions || []
  return positions.length > 0 && positions.every((position) => position.application_id)
})

const emails = computed(() => announcement.value?.apply_method?.emails || [])
const applyLinks = computed(() => announcement.value?.apply_method?.links || [])

function formatDateTime(value: string | null): string {
  if (!value) return '—'
  return value.replace('T', ' ').slice(0, 16)
}

async function load() {
  loading.value = true
  errorMessage.value = ''
  try {
    announcement.value = await getJobAnnouncement(announcementId.value)
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  } finally {
    loading.value = false
  }
}

function openApplication(position?: JobPositionItem) {
  presets.value = position ? [position.id] : []
  applicationOpen.value = true
}

/** Module 1 → module 3 hand-off: optimise a resume against this announcement. */
async function openResumeOptimizer() {
  if (!announcement.value) return
  try {
    const result = await listResumes({ page_size: 100 })
    resumes.value = result.items
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
    return
  }
  if (!resumes.value.length) {
    ElMessage.warning('还没有简历，请先在「我的简历」导入一份')
    await router.push('/workspace/resumes')
    return
  }
  selectedResumeId.value = resumes.value[0].id
  resumePickerOpen.value = true
}

function confirmResumeOptimizer() {
  if (!announcement.value || !selectedResumeId.value) return
  resumePickerOpen.value = false
  void router.push({
    path: `/workspace/resumes/${selectedResumeId.value}`,
    query: { announcement: announcement.value.id, optimize: '1' },
  })
}

async function afterCreated() {
  await load()
}

async function toggleDeferred() {
  if (!announcement.value) return
  if (announcement.value.mark_status === 'deferred') {
    try {
      await markJob(announcement.value.id, { status: 'none' })
      ElMessage.success('已取消暂不投递')
      await load()
    } catch (error) {
      ElMessage.error(getApiErrorMessage(error))
    }
    return
  }

  const result = await ElMessageBox.prompt('可以记录暂不投递的原因。', '暂不投递', {
    confirmButtonText: '确认',
    cancelButtonText: '取消',
    inputPlaceholder: '例如：等春招 / 岗位不匹配',
    inputValidator: (value: string) => value.length <= 500 || '最多 500 个字符',
  })
    .then(({ value }) => ({ confirmed: true, note: value }))
    .catch(() => ({ confirmed: false, note: '' }))
  if (!result.confirmed) return

  try {
    await markJob(announcement.value.id, { status: 'deferred', note: result.note || null })
    ElMessage.success('已标记为暂不投递')
    await load()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

onMounted(load)
</script>

<template>
  <main class="page">
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

    <template v-else-if="announcement">
      <RouterLink class="back-link" to="/workspace/jobs">
        <el-icon><ArrowLeft /></el-icon>
        返回职位信息
      </RouterLink>

      <header class="detail-hero">
        <div>
          <p class="eyebrow">{{ announcement.company.name }}</p>
          <h1>{{ announcement.title }}</h1>
          <div class="detail-tags">
            <el-tag v-if="announcement.recruitment_type" size="small" effect="plain">
              {{ announcement.recruitment_type }}
            </el-tag>
            <el-tag v-if="announcement.target_cohort" size="small" effect="plain">
              {{ announcement.target_cohort }}
            </el-tag>
            <el-tag v-if="announcement.deadline.text" size="small" type="warning" effect="plain">
              截止 {{ announcement.deadline.text }}
            </el-tag>
            <el-tag size="small" :type="rowStatusType" effect="plain">
              {{ announcement.mark_status_label }}
            </el-tag>
          </div>
          <p class="detail-subtitle">
            <span v-if="announcement.source.name">来源：{{ announcement.source.name }}</span>
            <span v-if="announcement.published_at">
              · 发布 {{ formatDateTime(announcement.published_at) }}
            </span>
            <span v-if="announcement.locations.length">
              · 地点 {{ announcement.locations.join('、') }}
            </span>
          </p>
        </div>
        <div class="detail-actions">
          <el-tooltip
            :disabled="!allPositionsApplied"
            content="该公告下所有岗位都已创建投递记录"
            placement="top"
          >
            <span>
              <el-button type="primary" :disabled="allPositionsApplied" @click="openApplication()">
                创建投递记录
              </el-button>
            </span>
          </el-tooltip>
          <el-button :icon="DocumentAdd" @click="openResumeOptimizer">用简历优化这个 JD</el-button>
          <el-button
            :disabled="announcement.positions.some((position) => position.application_id)"
            @click="toggleDeferred"
          >
            {{ announcement.mark_status === 'deferred' ? '取消暂不投递' : '暂不投递' }}
          </el-button>
          <a
            v-if="announcement.source.url"
            :href="announcement.source.url"
            target="_blank"
            rel="noreferrer noopener"
          >
            <el-button :icon="Link">原文链接</el-button>
          </a>
        </div>
      </header>

      <div class="detail-grid">
        <div class="detail-content">
          <section class="surface">
            <div class="table-card-head">
              <h2>岗位清单</h2>
              <span class="muted-note">{{ announcement.positions.length }} 个岗位</span>
            </div>
            <el-table :data="announcement.positions" class="position-table">
              <el-table-column label="岗位" min-width="180">
                <template #default="{ row }">
                  <strong>{{ row.title }}</strong>
                </template>
              </el-table-column>
              <el-table-column label="类别" width="120">
                <template #default="{ row }">{{ row.category || '—' }}</template>
              </el-table-column>
              <el-table-column label="地点" width="110">
                <template #default="{ row }">{{ row.city || '—' }}</template>
              </el-table-column>
              <el-table-column label="学历" width="100">
                <template #default="{ row }">{{ row.education || '—' }}</template>
              </el-table-column>
              <el-table-column label="我的状态" width="110">
                <template #default="{ row }">
                  <el-tag
                    v-if="row.application_status"
                    size="small"
                    :type="statusTagType(row.application_status)"
                    effect="plain"
                  >
                    {{ row.application_status_label || row.application_status }}
                  </el-tag>
                  <span v-else class="muted-note">未投递</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="120" align="right">
                <template #default="{ row }">
                  <el-button
                    link
                    type="primary"
                    :disabled="Boolean(row.application_id)"
                    @click="openApplication(row)"
                  >
                    {{ row.application_id ? '已投递' : '创建投递' }}
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </section>

          <section class="surface">
            <div class="table-card-head">
              <h2>公告全文</h2>
            </div>
            <pre class="raw-text">{{ announcement.raw_text }}</pre>
          </section>

          <section class="surface">
            <div class="table-card-head">
              <h2>出处</h2>
            </div>
            <dl class="fact-list">
              <div>
                <dt>来源渠道</dt>
                <dd>{{ announcement.source_channel }}</dd>
              </div>
              <div>
                <dt>来源名称</dt>
                <dd>{{ announcement.source.name || '—' }}</dd>
              </div>
              <div>
                <dt>原文链接</dt>
                <dd>
                  <a
                    v-if="announcement.source.url"
                    class="source-link"
                    :href="announcement.source.url"
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    {{ announcement.source.url }}
                  </a>
                  <span v-else>—</span>
                </dd>
              </div>
              <div>
                <dt>抓取时间</dt>
                <dd>{{ formatDateTime(announcement.snapshot_at) }}</dd>
              </div>
            </dl>
            <p class="panel-note">
              公告版权归原作者与发布方所有。这里只保存本机使用的结构化字段与正文快照，并始终保留原文链接；可按来源删除。
            </p>
          </section>
        </div>

        <aside class="detail-sidebar">
          <section class="surface">
            <h2>公司</h2>
            <dl class="fact-list">
              <div>
                <dt>公司名称</dt>
                <dd>{{ announcement.company.name }}</dd>
              </div>
              <div>
                <dt>公司类型</dt>
                <dd>{{ announcement.company.type || '—' }}</dd>
              </div>
              <div>
                <dt>公司规模</dt>
                <dd>{{ announcement.company.scale || '—' }}</dd>
              </div>
              <div>
                <dt>行业</dt>
                <dd>{{ announcement.company.industry || '—' }}</dd>
              </div>
            </dl>
          </section>

          <section class="surface">
            <h2>投递方式</h2>
            <ul v-if="emails.length || applyLinks.length" class="apply-list">
              <li v-for="email in emails" :key="email">
                <a class="source-link" :href="`mailto:${email}`">{{ email }}</a>
              </li>
              <li v-for="link in applyLinks" :key="link">
                <a class="source-link" :href="link" target="_blank" rel="noreferrer noopener">
                  {{ link }}
                </a>
              </li>
            </ul>
            <p v-else class="muted-note">正文中没有识别到邮箱或网申链接。</p>
            <p v-if="announcement.apply_method.note" class="panel-note">
              {{ announcement.apply_method.note }}
            </p>
          </section>

          <section class="surface">
            <h2>我的标记</h2>
            <p v-if="announcement.mark_status === 'deferred'" class="muted-note">
              暂不投递<template v-if="announcement.mark_note">：{{ announcement.mark_note }}</template>
            </p>
            <p v-else class="muted-note">暂无标记</p>
          </section>
        </aside>
      </div>

      <ApplicationFormDialog
        v-model="applicationOpen"
        :announcement="announcement"
        :preset-position-ids="presets"
        @created="afterCreated"
      />

      <el-dialog v-model="resumePickerOpen" title="用简历优化这个 JD" width="520px">
        <p class="panel-note">
          选择一份简历，打开工作台后会自动把它设为这份公告的目标岗位，并生成匹配报告与建议稿。
        </p>
        <el-select v-model="selectedResumeId" class="full-width" filterable>
          <el-option
            v-for="resume in resumes"
            :key="resume.id"
            :label="`${resume.candidate_name || resume.title} · v${resume.content_version}`"
            :value="resume.id"
          />
        </el-select>
        <template #footer>
          <el-button @click="resumePickerOpen = false">取消</el-button>
          <el-button type="primary" :disabled="!selectedResumeId" @click="confirmResumeOptimizer">
            打开简历工作台
          </el-button>
        </template>
      </el-dialog>
    </template>
  </main>
</template>
