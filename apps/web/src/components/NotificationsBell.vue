<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Bell } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

import { getApiErrorMessage } from '@/api/errors'
import {
  completeReminder,
  dismissReminder,
  getReminderSummary,
  listReminders,
  snoozeReminder,
} from '@/api/workspace'
import type { ReminderItem } from '@/types/workspace'

const router = useRouter()
const open = ref(false)
const loading = ref(false)
const items = ref<ReminderItem[]>([])
const pending = ref(0)
const dueNow = ref(0)
const acting = ref('')

const RULE_LABELS: Record<string, string> = {
  follow_up_due: '跟进',
  interview_soon: '面试',
  no_reply_stale: '久无回音',
  offer_reply_due: 'Offer 答复',
}

async function refreshSummary() {
  try {
    const summary = await getReminderSummary()
    pending.value = summary.pending
    dueNow.value = summary.due_now
  } catch {
    /* signed out / offline: keep the bell quiet */
  }
}

async function load() {
  loading.value = true
  try {
    const result = await listReminders()
    items.value = result.items
    pending.value = result.pending
    dueNow.value = result.due_now
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    loading.value = false
  }
}

watch(open, (visible) => {
  if (visible) void load()
})

async function act(kind: 'done' | 'dismiss' | 'snooze', item: ReminderItem) {
  acting.value = item.id
  try {
    if (kind === 'done') await completeReminder(item.id)
    else if (kind === 'dismiss') await dismissReminder(item.id)
    else await snoozeReminder(item.id, 24)
    await load()
    if (kind !== 'snooze') ElMessage.success('已处理')
    else ElMessage.success('24 小时后再提醒')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    acting.value = ''
  }
}

function openItem(item: ReminderItem) {
  open.value = false
  if (item.application_id) {
    void router.push(`/workspace/applications/${item.application_id}`)
  }
}

function formatDue(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = (input: number) => String(input).padStart(2, '0')
  return `${date.getMonth() + 1}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

onMounted(() => {
  void refreshSummary()
  void load()
})
</script>

<template>
  <el-popover v-model:visible="open" placement="bottom-end" :width="380" trigger="click">
    <template #reference>
      <el-badge
        :value="pending"
        :hidden="pending === 0"
        :type="dueNow > 0 ? 'danger' : 'primary'"
        class="reminder-badge"
      >
        <el-button text :icon="Bell" aria-label="提醒" />
      </el-badge>
    </template>

    <div class="reminder-panel">
      <header class="reminder-head">
        <strong>提醒</strong>
        <small v-if="pending">{{ pending }} 条待处理 · {{ dueNow }} 条已到期</small>
        <small v-else>暂无待处理提醒</small>
      </header>

      <el-skeleton v-if="loading" :rows="4" animated />
      <el-empty v-else-if="!items.length" description="没有需要处理的提醒" :image-size="54" />
      <ul v-else class="reminder-list">
        <li v-for="item in items" :key="item.id" class="reminder-item">
          <div class="reminder-item-main">
            <div class="reminder-item-title">
              <el-tag size="small" effect="plain" type="warning">
                {{ RULE_LABELS[item.rule_type] || item.rule_type }}
              </el-tag>
              <button type="button" class="reminder-title-btn" @click="openItem(item)">
                {{ item.title }}
              </button>
            </div>
            <p v-if="item.body" class="reminder-body">{{ item.body }}</p>
            <small class="muted-note">到期 {{ formatDue(item.due_at) }}</small>
          </div>
          <div class="reminder-actions">
            <el-button size="small" link type="primary" :loading="acting === item.id" @click="act('done', item)">
              完成
            </el-button>
            <el-button size="small" link @click="act('snooze', item)">稍后</el-button>
            <el-button size="small" link type="danger" @click="act('dismiss', item)">忽略</el-button>
          </div>
        </li>
      </ul>
    </div>
  </el-popover>
</template>
