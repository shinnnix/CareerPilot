<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, UploadFilled } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'

import { getApiErrorMessage } from '@/api/errors'
import {
  downloadJobCatalogCsv,
  getJobAnnouncement,
  getJobFacets,
  listJobCatalog,
  markJob,
  markJobsBatch,
} from '@/api/workspace'
import ApplicationFormDialog from '@/components/ApplicationFormDialog.vue'
import ColumnSettings from '@/components/ColumnSettings.vue'
import ImportJobDialog from '@/components/ImportJobDialog.vue'
import JobFilterPanel from '@/components/JobFilterPanel.vue'
import { useJobTableStore } from '@/stores/jobTable'
import { saveBlob, todayStamp } from '@/utils/download'
import type {
  JobAnnouncement,
  JobCatalogParams,
  JobFacets,
  JobFilters,
  JobRow,
} from '@/types/workspace'

const ADVANCED_KEY = 'careerpilot.jobs.advanced'
const PAGE_SIZES = [20, 50, 100]

const EMPTY_FACETS: JobFacets = {
  company_types: [],
  recruitment_types: [],
  target_cohorts: [],
  locations: [],
  job_categories: [],
  statuses: [],
}

const route = useRoute()
const router = useRouter()
const tableStore = useJobTableStore()

const rows = ref<JobRow[]>([])
const total = ref(0)
const pageCount = ref(1)
const loading = ref(false)
const errorMessage = ref('')
const facets = ref<JobFacets>(EMPTY_FACETS)
const importOpen = ref(false)
const advancedOpen = ref(readAdvanced())
const actionLoading = ref('')
const exporting = ref(false)
const selectedRows = ref<JobRow[]>([])
const batching = ref(false)

const filters = reactive<JobFilters>(readFilters())

const applicationOpen = ref(false)
const applicationAnnouncement = ref<JobAnnouncement | null>(null)
const applicationPresets = ref<string[]>([])

const visibleColumns = computed(() => new Set(tableStore.visible))

function readAdvanced(): boolean {
  try {
    return localStorage.getItem(ADVANCED_KEY) === '1'
  } catch {
    return false
  }
}

function setAdvanced(value: boolean) {
  advancedOpen.value = value
  try {
    localStorage.setItem(ADVANCED_KEY, value ? '1' : '0')
  } catch {
    /* storage unavailable */
  }
}

function readFilters(): JobFilters {
  const query = route.query
  const text = (key: string) => (typeof query[key] === 'string' ? (query[key] as string) : '')
  return {
    keyword: text('keyword'),
    company: text('company'),
    status: text('status'),
    company_type: text('company_type'),
    recruitment_type: text('recruitment_type'),
    target_cohort: text('target_cohort'),
    location: text('location'),
    job_category: text('job_category'),
    sort: (text('sort') || 'updated_desc') as JobFilters['sort'],
    page: Number(query.page) || 1,
    page_size: Number(query.page_size) || 20,
  }
}

function toParams(): JobCatalogParams {
  const params: JobCatalogParams = {
    sort: filters.sort,
    page: filters.page,
    page_size: filters.page_size,
  }
  const optional: (keyof JobFilters)[] = [
    'keyword',
    'company',
    'status',
    'company_type',
    'recruitment_type',
    'target_cohort',
    'location',
    'job_category',
  ]
  optional.forEach((key) => {
    const value = filters[key]
    if (typeof value === 'string' && value.trim()) {
      ;(params as Record<string, unknown>)[key] = value.trim()
    }
  })
  return params
}

async function syncRoute() {
  const query: Record<string, string> = {}
  Object.entries(toParams()).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return
    if (key === 'page' && Number(value) === 1) return
    if (key === 'page_size' && Number(value) === 20) return
    if (key === 'sort' && value === 'updated_desc') return
    query[key] = String(value)
  })
  await router.replace({ query })
}

async function load() {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await listJobCatalog(toParams())
    rows.value = result.items
    total.value = result.total
    pageCount.value = result.page_count
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function loadFacets() {
  try {
    facets.value = await getJobFacets()
  } catch {
    facets.value = EMPTY_FACETS
  }
}

function applyFilters(next: JobFilters) {
  Object.assign(filters, next)
}

async function search() {
  filters.page = 1
  await syncRoute()
  await load()
}

async function reset() {
  Object.assign(filters, {
    keyword: '',
    company: '',
    status: '',
    company_type: '',
    recruitment_type: '',
    target_cohort: '',
    location: '',
    job_category: '',
    page: 1,
  })
  await syncRoute()
  await load()
}

async function changePage(next: number) {
  filters.page = next
  await syncRoute()
  await load()
}

async function changePageSize(size: number) {
  filters.page_size = size
  filters.page = 1
  await syncRoute()
  await load()
}

function openDetail(row: JobRow) {
  void router.push(`/workspace/jobs/${row.id}`)
}

function formatDate(value: string | null): string {
  if (!value) return '—'
  return value.slice(0, 10)
}

function statusTagType(status: string): 'success' | 'warning' | 'info' | 'danger' | 'primary' {
  if (status === 'offer') return 'success'
  if (status === 'rejected') return 'danger'
  if (status === 'applied' || status === 'written_test' || status === 'interview_done' || status === 'interview') {
    return status === 'applied' ? 'primary' : 'warning'
  }
  return 'info'
}

function stageSummaryText(row: JobRow): string {
  return Object.entries(row.stage_summary)
    .map(([label, count]) => `${label} ${count}`)
    .join(' · ')
}

/** Every position of this announcement already has an application row. */
function allPositionsApplied(row: JobRow): boolean {
  return row.position_count > 0 && row.applied_position_count >= row.position_count
}

function handleSelectionChange(rows: JobRow[]) {
  selectedRows.value = rows
}

async function batchMark(status: 'deferred' | 'none') {
  if (!selectedRows.value.length) return
  batching.value = true
  try {
    await markJobsBatch({
      announcement_ids: selectedRows.value.map((row) => row.id),
      status,
    })
    ElMessage.success(status === 'deferred' ? '已批量标记暂不投递' : '已批量恢复')
    selectedRows.value = []
    await Promise.all([load(), loadFacets()])
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    batching.value = false
  }
}

async function createApplication(row: JobRow) {
  actionLoading.value = row.id
  try {
    applicationAnnouncement.value = await getJobAnnouncement(row.id)
    applicationPresets.value = []
    applicationOpen.value = true
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    actionLoading.value = ''
  }
}

async function afterApplicationCreated() {
  await Promise.all([load(), loadFacets()])
}

async function deferRow(row: JobRow) {
  if (row.mark_status === 'deferred') {
    try {
      await markJob(row.id, { status: 'none' })
      ElMessage.success('已取消暂不投递')
      await Promise.all([load(), loadFacets()])
    } catch (error) {
      ElMessage.error(getApiErrorMessage(error))
    }
    return
  }

  const result = await ElMessageBox.prompt('可以记录暂不投递的原因，之后可按状态筛回。', '暂不投递', {
    confirmButtonText: '确认',
    cancelButtonText: '取消',
    inputPlaceholder: '例如：等春招 / 岗位不匹配',
    inputValidator: (value: string) => value.length <= 500 || '最多 500 个字符',
  })
    .then(({ value }) => ({ confirmed: true, note: value }))
    .catch(() => ({ confirmed: false, note: '' }))
  if (!result.confirmed) return

  try {
    await markJob(row.id, { status: 'deferred', note: result.note || null })
    ElMessage.success('已标记为暂不投递')
    await Promise.all([load(), loadFacets()])
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

function exportCsv() {
  void downloadCsv()
}

async function downloadCsv() {
  exporting.value = true
  try {
    const blob = await downloadJobCatalogCsv(toParams())
    saveBlob(blob, `职位信息-${todayStamp()}.csv`)
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    exporting.value = false
  }
}

function afterImported(announcement: JobAnnouncement) {
  void Promise.all([load(), loadFacets()])
  void router.push(`/workspace/jobs/${announcement.id}`)
}

onMounted(async () => {
  if (route.query.import === '1') importOpen.value = true
  await Promise.all([tableStore.load(), loadFacets(), load()])
})
</script>

<template>
  <main class="page">
    <header class="page-head">
      <div>
        <p class="eyebrow">职位信息</p>
        <h1>发现适合你的下一站</h1>
        <p class="page-desc">筛选职位、记录机会，把每一次选择都整理得井井有条。</p>
      </div>
      <div class="page-head-actions">
        <el-button :icon="Download" :loading="exporting" @click="exportCsv">导出 CSV</el-button>
        <el-button type="primary" :icon="UploadFilled" @click="importOpen = true">
          导入职位
        </el-button>
      </div>
    </header>

    <div class="data-bar">
      <span><strong>{{ total }}</strong> 条职位</span>
      <span class="data-bar-sep">·</span>
      <span>本页 {{ rows.length }} 条</span>
      <span class="data-bar-note">先筛选机会，再记录进展</span>
    </div>

    <JobFilterPanel
      :model-value="filters"
      :facets="facets"
      :advanced-open="advancedOpen"
      @update:model-value="applyFilters"
      @update:advanced-open="setAdvanced"
      @search="search"
      @reset="reset"
    />

    <section class="surface table-card">
      <div class="table-card-head">
        <h2>职位信息</h2>
        <div class="table-card-tools">
          <template v-if="selectedRows.length">
            <span class="muted-note">已选 {{ selectedRows.length }} 条</span>
            <el-button size="small" :loading="batching" @click="batchMark('deferred')">
              批量暂不投递
            </el-button>
            <el-button size="small" :loading="batching" @click="batchMark('none')">
              批量恢复
            </el-button>
          </template>
          <ColumnSettings
            :columns="tableStore.columns"
            :visible="tableStore.visible"
            @update:visible="tableStore.setVisible"
          />
          <span class="muted-note">共 {{ total }} 条</span>
        </div>
      </div>

      <el-skeleton v-if="loading" :rows="8" animated class="table-card-state" />

      <el-alert
        v-else-if="errorMessage"
        class="table-card-state"
        :title="errorMessage"
        type="error"
        :closable="false"
        show-icon
      >
        <el-button size="small" @click="load">重新加载</el-button>
      </el-alert>

      <el-empty v-else-if="!rows.length" description="还没有符合条件的职位">
        <el-button type="primary" :icon="UploadFilled" @click="importOpen = true">
          导入第一条职位
        </el-button>
      </el-empty>

      <template v-else>
        <el-table
          :data="rows"
          class="job-table"
          row-key="id"
          @row-click="openDetail"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="44" reserve-selection />
          <el-table-column
            v-if="visibleColumns.has('company_name')"
            label="公司名称"
            min-width="160"
          >
            <template #default="{ row }">
              <strong class="job-company">{{ row.company.name }}</strong>
            </template>
          </el-table-column>

          <el-table-column
            v-if="visibleColumns.has('company_type')"
            label="公司类型"
            width="104"
          >
            <template #default="{ row }">{{ row.company.type || '—' }}</template>
          </el-table-column>

          <el-table-column
            v-if="visibleColumns.has('company_scale')"
            label="公司规模"
            width="120"
          >
            <template #default="{ row }">{{ row.company.scale || '—' }}</template>
          </el-table-column>

          <el-table-column
            v-if="visibleColumns.has('recruitment_type')"
            label="招聘类型"
            width="104"
          >
            <template #default="{ row }">{{ row.recruitment_type || '—' }}</template>
          </el-table-column>

          <el-table-column
            v-if="visibleColumns.has('target_cohort')"
            label="招聘对象"
            width="104"
          >
            <template #default="{ row }">{{ row.target_cohort || '不限' }}</template>
          </el-table-column>

          <el-table-column
            v-if="visibleColumns.has('location')"
            label="工作地点"
            min-width="140"
          >
            <template #default="{ row }">
              {{ row.locations.length ? row.locations.join('、') : '—' }}
            </template>
          </el-table-column>

          <el-table-column v-if="visibleColumns.has('positions')" label="岗位" min-width="220">
            <template #default="{ row }">
              <div class="job-positions-cell">
                <span class="job-positions-text">{{ row.positions_preview || '—' }}</span>
                <RouterLink
                  class="cell-link"
                  :to="`/workspace/jobs/${row.id}`"
                  @click.stop
                >
                  查看岗位与公告 →
                </RouterLink>
              </div>
            </template>
          </el-table-column>

          <el-table-column
            v-if="visibleColumns.has('updated_at')"
            label="更新时间"
            width="112"
          >
            <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
          </el-table-column>

          <el-table-column v-if="visibleColumns.has('deadline')" label="投递截止" width="120">
            <template #default="{ row }">
              <span :class="{ 'is-urgent': row.deadline.at && row.deadline.at < new Date().toISOString().slice(0, 10) }">
                {{ row.deadline.text || '—' }}
              </span>
            </template>
          </el-table-column>

          <el-table-column
            v-if="visibleColumns.has('announcement')"
            label="招聘公告"
            width="110"
          >
            <template #default="{ row }">
              <RouterLink class="cell-link" :to="`/workspace/jobs/${row.id}`" @click.stop>
                查看公告 →
              </RouterLink>
            </template>
          </el-table-column>

          <el-table-column v-if="visibleColumns.has('mark_status')" label="状态" width="150">
            <template #default="{ row }">
              <div class="job-status-cell">
                <el-tag size="small" :type="statusTagType(row.mark_status)" effect="plain">
                  {{ row.mark_status_label }}
                </el-tag>
                <el-tooltip
                  v-if="row.applied_position_count > 0 && row.position_count > 1"
                  :content="stageSummaryText(row)"
                  placement="top"
                >
                  <span class="muted-note">
                    {{ row.applied_position_count }}/{{ row.position_count }} 个岗位已投递
                  </span>
                </el-tooltip>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="188" fixed="right">
            <template #default="{ row }">
              <el-tooltip
                :disabled="!allPositionsApplied(row)"
                content="该公告下所有岗位都已创建投递记录"
                placement="top"
              >
                <span>
                  <el-button
                    link
                    type="primary"
                    :disabled="allPositionsApplied(row)"
                    :loading="actionLoading === row.id"
                    @click.stop="createApplication(row)"
                  >
                    创建投递记录
                  </el-button>
                </span>
              </el-tooltip>
              <el-tooltip
                :disabled="!row.application_ids.length"
                content="已有投递记录，状态以投递为准"
                placement="top"
              >
                <span>
                  <el-button
                    link
                    :disabled="row.application_ids.length > 0"
                    @click.stop="deferRow(row)"
                  >
                    {{ row.mark_status === 'deferred' ? '恢复' : '暂不投递' }}
                  </el-button>
                </span>
              </el-tooltip>
            </template>
          </el-table-column>
        </el-table>

        <div class="table-card-foot">
          <el-pagination
            layout="prev, pager, next, sizes, jumper"
            :current-page="filters.page"
            :page-size="filters.page_size"
            :page-sizes="PAGE_SIZES"
            :total="total"
            :pager-count="5"
            background
            @current-change="changePage"
            @size-change="changePageSize"
          />
        </div>
      </template>
    </section>

    <p v-if="pageCount > 1" class="page-hint">第 {{ filters.page }} / {{ pageCount }} 页</p>

    <ImportJobDialog v-model="importOpen" @imported="afterImported" />
    <ApplicationFormDialog
      v-model="applicationOpen"
      :announcement="applicationAnnouncement"
      :preset-position-ids="applicationPresets"
      @created="afterApplicationCreated"
    />
  </main>
</template>
