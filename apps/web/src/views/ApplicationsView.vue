<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Plus } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'

import { getApiErrorMessage } from '@/api/errors'
import {
  deleteApplicationRecord,
  downloadApplicationCsv,
  getApplicationMetrics,
  listApplicationRecords,
  updateApplicationRecord,
} from '@/api/workspace'
import ApplicationManualDialog from '@/components/ApplicationManualDialog.vue'
import { APPLICATION_STATUSES, APPLICATION_STATUS_LABELS } from '@/types/applications'
import { saveBlob, todayStamp } from '@/utils/download'
import type {
  ApplicationFilters,
  ApplicationListParams,
  ApplicationMetricsResponse,
  ApplicationRow,
} from '@/types/workspace'
import { formatDate, nextStatuses, statusTagType } from '@/utils/applicationStatus'

const PAGE_SIZES = [20, 50, 100]
const EMPTY_METRICS: ApplicationMetricsResponse = {
  total: 0,
  by_status: {},
  due_follow_ups: 0,
  terminal: 0,
  active: 0,
}

const route = useRoute()
const router = useRouter()

const rows = ref<ApplicationRow[]>([])
const total = ref(0)
const pageCount = ref(1)
const loading = ref(false)
const errorMessage = ref('')
const metrics = ref<ApplicationMetricsResponse>(EMPTY_METRICS)
const dialogOpen = ref(false)
const actionLoading = ref('')
const exporting = ref(false)

const filters = reactive<ApplicationFilters>(readFilters())

const statusOptions = computed(() =>
  APPLICATION_STATUSES.map((status) => ({
    value: status,
    label: APPLICATION_STATUS_LABELS[status],
    count: metrics.value.by_status[status] ?? 0,
  })),
)

function readFilters(): ApplicationFilters {
  const query = route.query
  const text = (key: string) => (typeof query[key] === 'string' ? (query[key] as string) : '')
  return {
    keyword: text('keyword'),
    status: text('status'),
    sort: (text('sort') || 'applied_desc') as ApplicationFilters['sort'],
    page: Number(query.page) || 1,
    page_size: Number(query.page_size) || 20,
  }
}

function toParams(): ApplicationListParams {
  const params: ApplicationListParams = {
    sort: filters.sort,
    page: filters.page,
    page_size: filters.page_size,
  }
  if (filters.keyword.trim()) params.keyword = filters.keyword.trim()
  if (filters.status) params.status = filters.status
  return params
}

async function syncRoute() {
  const query: Record<string, string> = {}
  const params = toParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return
    if (key === 'page' && Number(value) === 1) return
    if (key === 'page_size' && Number(value) === 20) return
    if (key === 'sort' && value === 'applied_desc') return
    query[key] = String(value)
  })
  await router.replace({ query })
}

async function load() {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await listApplicationRecords(toParams())
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

async function loadMetrics() {
  try {
    metrics.value = await getApplicationMetrics()
  } catch {
    metrics.value = EMPTY_METRICS
  }
}

async function search() {
  filters.page = 1
  await syncRoute()
  await load()
}

async function reset() {
  Object.assign(filters, { keyword: '', status: '', page: 1 })
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

function openDetail(row: ApplicationRow) {
  void router.push(`/workspace/applications/${row.id}`)
}

async function changeStatus(row: ApplicationRow, status: string) {
  actionLoading.value = row.id
  try {
    await updateApplicationRecord(row.id, { status, row_version: row.row_version })
    ElMessage.success(`已更新为「${APPLICATION_STATUS_LABELS[status as keyof typeof APPLICATION_STATUS_LABELS]}」`)
    await Promise.all([load(), loadMetrics()])
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    actionLoading.value = ''
  }
}

async function removeRow(row: ApplicationRow) {
  const confirmed = await ElMessageBox.confirm(
    `删除「${row.company_name} · ${row.position_title}」后不可恢复，确认继续？`,
    '删除投递记录',
    { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
  )
    .then(() => true)
    .catch(() => false)
  if (!confirmed) return
  try {
    await deleteApplicationRecord(row.id)
    ElMessage.success('已删除')
    await Promise.all([load(), loadMetrics()])
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
    const blob = await downloadApplicationCsv(toParams())
    saveBlob(blob, `投递记录-${todayStamp()}.csv`)
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    exporting.value = false
  }
}

async function afterCreated() {
  await Promise.all([load(), loadMetrics()])
}

function rowClassName({ row }: { row: ApplicationRow }) {
  return row.is_terminal ? 'row-terminal' : ''
}

onMounted(async () => {
  await Promise.all([load(), loadMetrics()])
})
</script>

<template>
  <main class="page">
    <header class="page-head">
      <div>
        <p class="eyebrow">投递记录</p>
        <h1>每一份投递，都有进展</h1>
        <p class="page-desc">把申请、笔试与面试放在一处，下一步更清晰。</p>
      </div>
      <div class="page-head-actions">
        <el-button :icon="Download" :loading="exporting" @click="exportCsv">导出 CSV</el-button>
        <el-button type="primary" :icon="Plus" @click="dialogOpen = true">手动新增</el-button>
      </div>
    </header>

    <div class="data-bar">
      <span><strong>{{ total }}</strong> 条投递</span>
      <span class="data-bar-sep">·</span>
      <span>进行中 {{ metrics.active }}</span>
      <span class="data-bar-sep">·</span>
      <span>已结束 {{ metrics.terminal }}</span>
      <span v-if="metrics.due_follow_ups" class="data-bar-alert">
        待跟进 {{ metrics.due_follow_ups }}
      </span>
    </div>

    <section class="surface filter-card">
      <div class="filter-row">
        <el-input
          v-model="filters.keyword"
          class="filter-input"
          placeholder="搜索公司 / 岗位 / 联系人 / 备注"
          clearable
          @keyup.enter="search"
        />
        <el-select v-model="filters.status" class="filter-select" placeholder="全部状态" clearable>
          <el-option
            v-for="option in statusOptions"
            :key="option.value"
            :label="`${option.label}（${option.count}）`"
            :value="option.value"
          />
        </el-select>
        <div class="filter-actions">
          <el-button type="primary" @click="search">搜索</el-button>
          <el-button @click="reset">重置</el-button>
        </div>
      </div>
    </section>

    <section class="surface table-card">
      <div class="table-card-head">
        <h2>投递记录</h2>
        <div class="table-card-tools">
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

      <el-empty v-else-if="!rows.length" description="还没有投递记录">
        <p class="page-hint">先在职位信息里挑好机会，或者直接手动补一条。</p>
        <div class="empty-actions">
          <el-button @click="router.push('/workspace/jobs')">去职位信息</el-button>
          <el-button type="primary" :icon="Plus" @click="dialogOpen = true">手动新增</el-button>
        </div>
      </el-empty>

      <template v-else>
        <el-table
          :data="rows"
          class="job-table application-table"
          :row-class-name="rowClassName"
          @row-click="openDetail"
        >
          <el-table-column label="公司" min-width="160">
            <template #default="{ row }">
              <strong class="job-company">{{ row.company_name }}</strong>
            </template>
          </el-table-column>

          <el-table-column label="岗位" min-width="180">
            <template #default="{ row }">
              <span class="cell-link" @click.stop="openDetail(row)">{{ row.position_title }}</span>
            </template>
          </el-table-column>

          <el-table-column label="状态" width="112">
            <template #default="{ row }">
              <el-tag size="small" :type="statusTagType(row.status)" effect="plain">
                {{ row.status_label }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column label="投递日期" width="112">
            <template #default="{ row }">{{ formatDate(row.applied_at) }}</template>
          </el-table-column>

          <el-table-column label="跟进日期" width="120">
            <template #default="{ row }">
              <span :class="{ 'is-urgent': row.follow_up_due }">
                {{ formatDate(row.follow_up_at) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="渠道" width="112">
            <template #default="{ row }">{{ row.channel || '—' }}</template>
          </el-table-column>

          <el-table-column label="联系人" min-width="120">
            <template #default="{ row }">
              <div class="contact-cell">
                <span>{{ row.contact_name || '—' }}</span>
                <small v-if="row.contact_info">{{ row.contact_info }}</small>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="196" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click.stop="openDetail(row)">详情</el-button>
              <el-dropdown
                v-if="nextStatuses(row.status).length"
                trigger="click"
                @command="(status: string) => changeStatus(row, status)"
              >
                <el-button link :loading="actionLoading === row.id" @click.stop>
                  更新状态
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item v-for="status in nextStatuses(row.status)" :key="status" :command="status">
                      {{ APPLICATION_STATUS_LABELS[status] }}
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <el-button link type="danger" @click.stop="removeRow(row)">删除</el-button>
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

    <ApplicationManualDialog v-model="dialogOpen" @created="afterCreated" />
  </main>
</template>
