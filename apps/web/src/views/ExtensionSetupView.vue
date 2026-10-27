<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Check, Connection, Download, Link, Refresh } from '@element-plus/icons-vue'

import { useProfileStore } from '@/stores/profile'
import { SYNC_CHANNEL_HINTS, SYNC_CHANNEL_LABELS } from '@/types/profile'

const store = useProfileStore()

const probing = ref(false)
const healthStatus = ref<'unknown' | 'ok' | 'down'>('unknown')
const healthDetail = ref('')

const apiBase = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const origin = computed(() => {
  if (apiBase.startsWith('http')) return apiBase.replace(/\/api\/v1\/?$/, '')
  return window.location.origin
})
const healthUrl = computed(() => `${origin.value}/health`)

const steps = [
  {
    title: '下载并解压扩展',
    detail: '扩展源码在仓库的 apps/autofill-extension，解压到本地任意目录。',
  },
  {
    title: '加载已解压的扩展',
    detail: '打开 chrome://extensions，开启右上角「开发者模式」，点「加载已解压的扩展程序」，选中该目录。',
  },
  {
    title: '复制扩展 ID',
    detail: '扩展卡片上会显示一串 32 位 ID，复制后回到「网申个人信息」页填入，即可启用直连通道。',
  },
  {
    title: '填好个人信息并同步',
    detail: '在「网申个人信息」点「同步到插件」，扩展弹窗里就能看到同一份数据。',
  },
]

const boundaries = [
  '只填充后端标记为 ready 的高置信字段',
  '开放题、文件上传、敏感字段一律留给人工确认',
  '永不自动点击提交按钮',
  'Token 与个人信息只存在本机 chrome.storage.local',
]

onMounted(() => {
  store.detectChannel()
  void probe()
})

async function probe(): Promise<void> {
  probing.value = true
  try {
    const response = await fetch(healthUrl.value, { headers: { Accept: 'application/json' } })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const data = (await response.json()) as { status?: string; service?: string }
    healthStatus.value = 'ok'
    healthDetail.value = `${data.service ?? 'CareerPilot'} · ${data.status ?? 'ok'}`
  } catch (error) {
    healthStatus.value = 'down'
    healthDetail.value = (error as Error).message
  } finally {
    probing.value = false
  }
}

function copyId(): void {
  const id = store.extensionId.trim()
  if (!id) {
    ElMessage.warning('还没有填写扩展 ID')
    return
  }
  void navigator.clipboard?.writeText(id)
  ElMessage.success('已复制扩展 ID')
}
</script>

<template>
  <main class="page">
    <header class="page-head">
      <div>
        <p class="eyebrow">更多工具</p>
        <h1>网申填写插件</h1>
        <p class="page-desc">
          插件负责在招聘网站上读取表单、把字段交给 CareerPilot 生成填写计划，再逐项填回。
          它不会替你提交，也不会猜开放题的答案。
        </p>
      </div>
      <div class="page-head-actions">
        <el-button :icon="Refresh" :loading="probing" @click="probe">重新检测</el-button>
        <RouterLink to="/workspace/profile">
          <el-button type="primary" :icon="Link">去同步个人信息</el-button>
        </RouterLink>
      </div>
    </header>

    <section class="surface ext-status">
      <div class="ext-status-row">
        <div>
          <p class="eyebrow">后端连接</p>
          <h2 class="ext-status-value">
            <el-icon v-if="healthStatus === 'ok'" class="ext-ok"><Check /></el-icon>
            <el-icon v-else class="ext-pending"><Connection /></el-icon>
            <span v-if="healthStatus === 'ok'">已连接</span>
            <span v-else-if="healthStatus === 'down'">未连接</span>
            <span v-else>检测中</span>
          </h2>
          <p class="muted-note">{{ healthUrl }}</p>
          <p v-if="healthDetail" class="muted-note">{{ healthDetail }}</p>
        </div>
        <div>
          <p class="eyebrow">同步通道</p>
          <h2 class="ext-status-value">{{ SYNC_CHANNEL_LABELS[store.channel] }}</h2>
          <p class="muted-note">{{ SYNC_CHANNEL_HINTS[store.channel] }}</p>
        </div>
        <div>
          <p class="eyebrow">扩展 ID</p>
          <h2 class="ext-status-value ext-id">{{ store.extensionId || '未填写' }}</h2>
          <el-button size="small" text :icon="Download" @click="copyId">复制</el-button>
        </div>
      </div>
    </section>

    <section class="surface ext-card">
      <div class="table-card-head">
        <h2>安装步骤</h2>
        <span class="muted-note">Manifest V3 · 本地加载</span>
      </div>
      <ol class="ext-steps">
        <li v-for="(step, index) in steps" :key="step.title">
          <span class="ext-step-index">{{ index + 1 }}</span>
          <div>
            <strong>{{ step.title }}</strong>
            <p class="muted-note">{{ step.detail }}</p>
          </div>
        </li>
      </ol>
      <p class="muted-note">
        源码目录：<code>apps/autofill-extension</code>。修改后回到 chrome://extensions
        点卡片上的刷新即可，无需重新安装。
      </p>
    </section>

    <section class="surface ext-card">
      <div class="table-card-head">
        <h2>安全边界</h2>
      </div>
      <ul class="ext-boundaries">
        <li v-for="item in boundaries" :key="item">
          <el-icon class="ext-ok"><Check /></el-icon>
          <span>{{ item }}</span>
        </li>
      </ul>
      <el-alert type="warning" :closable="false" show-icon
        title="插件只是自动化到「填完」为止"
        description="提交前的最后一步永远由你自己完成；填错的字段请在页面上手动改正。"
      />
    </section>
  </main>
</template>
