<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { getApplication, listApplications, updateApplication } from '@/api/applications'
import { getApiErrorMessage } from '@/api/errors'
import type { ApplicationDetail, ApplicationStatus, ApplicationSummary } from '@/types/applications'

const applications = ref<ApplicationSummary[]>([])
const selected = ref<ApplicationDetail | null>(null)
const loading = ref(false)
const drawerOpen = ref(false)

const columns: { status: ApplicationStatus; label: string }[] = [
  { status: 'saved', label: '已收藏' },
  { status: 'preparing', label: '准备中' },
  { status: 'applied', label: '已投递' },
  { status: 'interview', label: '面试中' },
  { status: 'offer', label: 'Offer' },
  { status: 'rejected', label: '未通过' },
]

const grouped = computed(() =>
  Object.fromEntries(columns.map((column) => [column.status, applications.value.filter((item) => item.status === column.status)])),
)

const nextStatuses: Record<ApplicationStatus, ApplicationStatus[]> = {
  saved: ['preparing', 'applied', 'withdrawn'],
  preparing: ['saved', 'applied', 'withdrawn'],
  applied: ['interview', 'rejected', 'withdrawn'],
  interview: ['offer', 'rejected', 'withdrawn'],
  offer: ['withdrawn'],
  rejected: [],
  withdrawn: [],
}

async function load() {
  loading.value = true
  try {
    applications.value = (await listApplications()).items
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function changeStatus(item: ApplicationSummary, status: ApplicationStatus) {
  try {
    await updateApplication(item.id, { status, event_note: '在 Vue 申请看板更新' })
    await load()
    ElMessage.success('申请状态已更新')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

async function openTimeline(item: ApplicationSummary) {
  try {
    selected.value = await getApplication(item.id)
    drawerOpen.value = true
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

onMounted(load)
</script>

<template>
  <main class="page">
    <section class="applications-hero">
      <div><p class="eyebrow">APPLICATION PIPELINE</p><h1>从收藏到 Offer 的完整时间线</h1><p>状态转换由后端状态机校验，每次变化都会留下事件记录。</p></div>
      <strong>{{ applications.length }}</strong>
    </section>
    <el-skeleton v-if="loading" :rows="8" animated />
    <el-empty v-else-if="!applications.length" description="还没有申请记录，可从 Agent 创建" />
    <div v-else class="application-board">
      <section v-for="column in columns" :key="column.status" class="application-column">
        <header><strong>{{ column.label }}</strong><span>{{ grouped[column.status]?.length || 0 }}</span></header>
        <article v-for="item in grouped[column.status]" :key="item.id" class="application-card">
          <small>{{ item.company_name }}</small><h3>{{ item.job_title }}</h3>
          <p>{{ item.notes || '暂无备注' }}</p>
          <el-select v-if="nextStatuses[item.status].length" placeholder="更新状态" size="small" @change="changeStatus(item, $event)">
            <el-option v-for="status in nextStatuses[item.status]" :key="status" :label="status" :value="status" />
          </el-select>
          <el-button link type="primary" @click="openTimeline(item)">查看时间线</el-button>
        </article>
      </section>
    </div>
    <el-drawer v-model="drawerOpen" title="申请时间线" size="420px">
      <el-timeline v-if="selected">
        <el-timeline-item v-for="event in selected.events" :key="event.id" :timestamp="new Date(event.created_at).toLocaleString()">
          <strong>{{ event.event_type }}</strong><p>{{ event.from_status || '开始' }} → {{ event.to_status }}</p><small>{{ event.note }}</small>
        </el-timeline-item>
      </el-timeline>
    </el-drawer>
  </main>
</template>
