<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Delete, Refresh, Upload } from '@element-plus/icons-vue'

import { getAiMetrics, resetAiMetrics } from '@/api/settings'
import { useAiConfigStore } from '@/stores/ai-config'
import { usePreferencesStore } from '@/stores/preferences'
import {
  AI_FORMATS,
  AI_FORMAT_HINTS,
  AI_FORMAT_LABELS,
  AI_PRESETS,
  AI_TASKS,
  AI_TASK_LABELS,
  emptyAiConfig,
  maskApiKey,
  taskSupportsFormat,
} from '@/types/ai'
import type { AiConfig, AiFormat, AiMetrics, AiTask } from '@/types/ai'

const aiStore = useAiConfigStore()
const preferences = usePreferencesStore()

const activeTask = ref<AiTask>('chat')
const draft = reactive<AiConfig>(emptyAiConfig('openai'))
const metrics = ref<AiMetrics | null>(null)
const loadingMetrics = ref(false)

const currentMeta = computed(() => AI_TASKS.find((item) => item.key === activeTask.value)!)
const bound = computed(() => Boolean(aiStore.configFor(activeTask.value)))
const boundCount = computed(() => aiStore.boundTasks.length)
const formatBlocked = computed(() => !taskSupportsFormat(activeTask.value, draft.format))

const timezones = [
  'Asia/Shanghai',
  'Asia/Hong_Kong',
  'Asia/Singapore',
  'UTC',
  'America/New_York',
  'Europe/London',
]

function syncDraft(): void {
  const existing = aiStore.configFor(activeTask.value)
  Object.assign(draft, existing ?? emptyAiConfig('openai'))
}

watch(activeTask, syncDraft)

onMounted(() => {
  syncDraft()
  void loadMetrics()
})

function applyPreset(label: string): void {
  const preset = AI_PRESETS.find((item) => item.label === label)
  if (!preset) return
  draft.format = preset.format
  draft.baseUrl = preset.baseUrl
  draft.model = preset.model
}

async function loadMetrics(): Promise<void> {
  loadingMetrics.value = true
  try {
    metrics.value = await getAiMetrics()
  } catch {
    metrics.value = null
  } finally {
    loadingMetrics.value = false
  }
}

async function clearMetrics(): Promise<void> {
  try {
    await resetAiMetrics()
  } catch (error) {
    ElMessage.error((error as Error).message)
    return
  }
  await loadMetrics()
  ElMessage.success('已重置进程内调用统计')
}

async function testConnection(): Promise<void> {
  const result = await aiStore.test(activeTask.value, { ...draft })
  if (!result) return
  if (result.ok) {
    ElMessage.success(`连接成功 · ${result.model} · ${result.latency_ms}ms`)
    return
  }
  ElMessage.error(result.hint ?? result.error ?? '连接失败')
}

function bind(): void {
  const result = aiStore.bindTask(activeTask.value, { ...draft })
  if (!result.ok) {
    ElMessage.error(result.error ?? '绑定失败')
    return
  }
  ElMessage.success(`已绑定「${AI_TASK_LABELS[activeTask.value]}」`)
  syncDraft()
}

function unbind(): void {
  aiStore.unbindTask(activeTask.value)
  Object.assign(draft, emptyAiConfig(draft.format))
  ElMessage.success('已解绑，该任务回退到确定性实现')
}

async function copyFrom(from: AiTask): Promise<void> {
  const result = aiStore.copyTask(from, activeTask.value)
  if (!result.ok) {
    ElMessage.error(result.error ?? '复制失败')
    return
  }
  syncDraft()
  ElMessage.success(`已复制「${AI_TASK_LABELS[from]}」的配置`)
}

async function clearAll(): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '将删除浏览器里保存的所有 AI 配置与密钥，后端从未存过它们。确定继续？',
      '清空本地 AI 配置',
      { type: 'warning', confirmButtonText: '清空', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  aiStore.clearAll()
  Object.assign(draft, emptyAiConfig('openai'))
  ElMessage.success('已清空')
}

function downloadSettings(): void {
  const blob = new Blob([aiStore.exportSettings()], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = 'careerpilot-ai-settings.json'
  anchor.click()
  URL.revokeObjectURL(url)
  ElMessage.warning('导出文件包含 API Key 明文，请勿分享')
}

function onFormatChange(value: AiFormat): void {
  if (!taskSupportsFormat(activeTask.value, value)) {
    ElMessage.warning('Anthropic 没有 embedding/rerank 端点，该任务只能用 OpenAI 兼容格式')
    draft.format = 'openai'
  }
}
</script>

<template>
  <main class="page">
    <header class="page-head">
      <div>
        <p class="eyebrow">更多工具</p>
        <h1>AI 与设置</h1>
        <p class="page-desc">
          只有两种通信格式：OpenAI 兼容与 Anthropic。密钥只存在这台电脑的浏览器里，
          调用时按次透传，后端用完即丢，不写库也不写日志。
        </p>
      </div>
      <div class="page-head-actions">
        <el-button :icon="Upload" @click="downloadSettings">导出配置</el-button>
        <el-button type="danger" plain :icon="Delete" @click="clearAll">清空本地配置</el-button>
      </div>
    </header>

    <section class="surface settings-card">
      <div class="table-card-head">
        <h2>通用设置</h2>
        <span class="muted-note">只影响本机界面</span>
      </div>
      <el-form label-position="top" class="form-grid settings-form">
        <el-form-item label="时区">
          <el-select
            :model-value="preferences.general.timezone"
            style="width: 100%"
            @update:model-value="preferences.updateGeneral({ timezone: $event })"
          >
            <el-option v-for="zone in timezones" :key="zone" :label="zone" :value="zone" />
          </el-select>
        </el-form-item>
        <el-form-item label="通知方式">
          <el-radio-group
            :model-value="preferences.general.notifyChannel"
            @update:model-value="preferences.updateGeneral({ notifyChannel: $event })"
          >
            <el-radio-button value="in_app">站内</el-radio-button>
            <el-radio-button value="email">邮件</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="跟进提醒">
          <el-switch
            :model-value="preferences.general.remindersEnabled"
            active-text="开启"
            inactive-text="关闭"
            @update:model-value="preferences.updateGeneral({ remindersEnabled: Boolean($event) })"
          />
        </el-form-item>
      </el-form>
    </section>

    <section class="surface settings-card">
      <div class="table-card-head">
        <h2>AI 任务绑定</h2>
        <span class="muted-note">已绑定 {{ boundCount }} / {{ AI_TASKS.length }}</span>
      </div>

      <div class="settings-task-grid">
        <button
          v-for="task in AI_TASKS"
          :key="task.key"
          type="button"
          class="settings-task"
          :class="{ 'settings-task--active': task.key === activeTask }"
          @click="activeTask = task.key"
        >
          <span class="settings-task-head">
            <strong>{{ task.label }}</strong>
            <el-tag
              size="small"
              effect="plain"
              :type="aiStore.configFor(task.key) ? 'success' : 'info'"
            >
              {{ aiStore.configFor(task.key) ? '已绑定' : '确定性' }}
            </el-tag>
          </span>
          <small class="muted-note">{{ task.description }}</small>
        </button>
      </div>

      <el-form label-position="top" class="form-grid settings-form">
        <el-form-item label="接入预设">
          <el-select
            placeholder="选一个快速填入"
            clearable
            style="width: 100%"
            @update:model-value="applyPreset"
          >
            <el-option
              v-for="preset in AI_PRESETS"
              :key="preset.label"
              :label="`${preset.label} · ${preset.model}`"
              :value="preset.label"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="通信格式">
          <el-select
            v-model="draft.format"
            style="width: 100%"
            @change="onFormatChange"
          >
            <el-option
              v-for="format in AI_FORMATS"
              :key="format"
              :label="AI_FORMAT_LABELS[format]"
              :value="format"
            />
          </el-select>
          <p class="muted-note settings-hint">{{ AI_FORMAT_HINTS[draft.format] }}</p>
        </el-form-item>
        <el-form-item label="base_url">
          <el-input v-model="draft.baseUrl" placeholder="https://api.openai.com/v1" />
        </el-form-item>
        <el-form-item label="model">
          <el-input v-model="draft.model" placeholder="gpt-4o-mini" />
        </el-form-item>
        <el-form-item label="api_key">
          <el-input
            v-model="draft.apiKey"
            show-password
            placeholder="sk-..."
            autocomplete="off"
          />
          <p v-if="bound" class="muted-note settings-hint">
            当前已绑定：{{ maskApiKey(aiStore.configFor(activeTask)?.apiKey ?? '') }}
          </p>
        </el-form-item>
        <el-form-item label="温度">
          <el-slider v-model="draft.temperature" :min="0" :max="2" :step="0.1" show-input />
        </el-form-item>
        <el-form-item label="最大 token">
          <el-input-number v-model="draft.maxTokens" :min="1" :max="32000" :step="128" />
        </el-form-item>
      </el-form>

      <p v-if="formatBlocked" class="muted-note settings-hint">
        {{ currentMeta.label }} 只能用 OpenAI 兼容格式（Anthropic 无对应端点）。
      </p>

      <div class="settings-actions">
        <el-button :loading="aiStore.testing === activeTask" @click="testConnection">
          测试连接
        </el-button>
        <el-button type="primary" :disabled="formatBlocked" @click="bind">
          {{ bound ? '更新绑定' : '绑定到该任务' }}
        </el-button>
        <el-button v-if="bound" plain type="danger" @click="unbind">解绑</el-button>
        <el-dropdown v-if="boundCount" trigger="click">
          <el-button text>从其他任务复制</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                v-for="task in aiStore.boundTasks.filter((item) => item !== activeTask)"
                :key="task"
                @click="copyFrom(task)"
              >
                {{ AI_TASK_LABELS[task] }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>

      <el-alert
        v-if="aiStore.lastResult && !aiStore.lastResult.ok"
        class="settings-alert"
        type="error"
        :closable="false"
        show-icon
        :title="aiStore.lastResult.hint ?? '连接失败'"
        :description="aiStore.lastResult.error ?? ''"
      />
      <el-alert
        v-else-if="aiStore.lastResult?.ok"
        class="settings-alert"
        type="success"
        :closable="false"
        show-icon
        :title="`连接正常 · ${aiStore.lastResult.model} · ${aiStore.lastResult.latency_ms}ms`"
        :description="aiStore.lastResult.reply ?? ''"
      />
    </section>

    <section class="surface settings-card">
      <div class="table-card-head">
        <h2>调用统计</h2>
        <div class="table-card-tools">
          <el-button size="small" :icon="Refresh" :loading="loadingMetrics" @click="loadMetrics">
            刷新
          </el-button>
          <el-button size="small" text type="danger" @click="clearMetrics">重置</el-button>
        </div>
      </div>
      <div v-if="metrics" class="settings-metrics">
        <div>
          <p class="eyebrow">调用次数</p>
          <strong>{{ metrics.calls }}</strong>
        </div>
        <div>
          <p class="eyebrow">失败次数</p>
          <strong>{{ metrics.failures }}</strong>
        </div>
        <div>
          <p class="eyebrow">平均延迟</p>
          <strong>{{ Math.round(metrics.average_latency_ms) }}ms</strong>
        </div>
        <div>
          <p class="eyebrow">按格式</p>
          <strong class="settings-metrics-formats">
            <span v-for="(count, format) in metrics.by_format" :key="format">
              {{ format }} {{ count }}
            </span>
            <span v-if="!Object.keys(metrics.by_format).length" class="muted-note">暂无</span>
          </strong>
        </div>
      </div>
      <p v-else class="muted-note">统计只存在当前 API 进程内，重启即清零；不含 prompt 与密钥。</p>
    </section>

    <section class="surface settings-card">
      <div class="table-card-head">
        <h2>自动化脚本兜底</h2>
      </div>
      <p class="muted-note">
        不想在浏览器里填密钥时，可以在本机 <code>apps/api/.env</code> 设置
        <code>CAREERPILOT_AI_*</code>，仅对脚本与测试生效；浏览器配置优先。
      </p>
      <ul class="settings-env">
        <li><code>CAREERPILOT_AI_FORMAT</code> · <code>openai</code> / <code>anthropic</code></li>
        <li><code>CAREERPILOT_AI_BASE_URL</code> · 例如 <code>https://api.deepseek.com/v1</code></li>
        <li><code>CAREERPILOT_AI_MODEL</code> · 例如 <code>deepseek-chat</code></li>
        <li><code>CAREERPILOT_AI_API_KEY</code> · 只放在本机，不进版本库</li>
      </ul>
      <p class="muted-note">
        <el-icon><Check /></el-icon>
        未绑定的任务会自动回退到确定性实现：规则抽取、哈希 embedding、重叠重排，离线可用。
      </p>
    </section>
  </main>
</template>
