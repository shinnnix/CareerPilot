/**
 * AI configuration store (plan §5.3).
 *
 * Credentials live in `localStorage['careerpilot.ai.v1']` only. Every call that
 * needs a model passes them as an `X-AI-Config` header; nothing is uploaded for
 * storage.
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { clearAiSettings, readAiSettings, writeAiSettings } from '@/ai-storage'
import { testAiConnection } from '@/api/settings'
import {
  AI_SCHEMA_VERSION,
  AI_TASKS,
  emptyAiConfig,
  emptyAiSettings,
  isValidAiConfig,
  maskApiKey,
  taskSupportsFormat,
} from '@/types/ai'
import type { AiConfig, AiFormat, AiSettings, AiTask, AiTestResult } from '@/types/ai'

export const useAiConfigStore = defineStore('ai-config', () => {
  const settings = ref<AiSettings>(readAiSettings())
  const testing = ref<AiTask | null>(null)
  const lastResult = ref<AiTestResult | null>(null)

  const boundTasks = computed(() =>
    AI_TASKS.map((meta) => meta.key).filter((task) => Boolean(settings.value.tasks[task])),
  )
  const hasChat = computed(() => isValidAiConfig(settings.value.tasks.chat))
  const maskedKeys = computed(() => {
    const result: Partial<Record<AiTask, string>> = {}
    for (const task of boundTasks.value) {
      result[task] = maskApiKey(settings.value.tasks[task]?.apiKey ?? '')
    }
    return result
  })

  function reload(): void {
    settings.value = readAiSettings()
  }

  function persist(): void {
    settings.value.updatedAt = new Date().toISOString()
    writeAiSettings(settings.value)
  }

  function configFor(task: AiTask): AiConfig | null {
    const config = settings.value.tasks[task]
    return isValidAiConfig(config) ? (config as AiConfig) : null
  }

  function draftFor(task: AiTask, format: AiFormat = 'openai'): AiConfig {
    return configFor(task) ?? emptyAiConfig(format)
  }

  function bindTask(task: AiTask, config: AiConfig): { ok: boolean; error?: string } {
    if (!taskSupportsFormat(task, config.format)) {
      return { ok: false, error: 'Anthropic 格式不支持该任务，请改用 OpenAI 兼容格式' }
    }
    if (!isValidAiConfig(config)) {
      return { ok: false, error: 'base_url、model 与 api_key 都不能为空' }
    }
    settings.value.tasks = {
      ...settings.value.tasks,
      [task]: {
        ...config,
        baseUrl: config.baseUrl.trim().replace(/\/+$/, ''),
        model: config.model.trim(),
        apiKey: config.apiKey.trim(),
      },
    }
    persist()
    return { ok: true }
  }

  function unbindTask(task: AiTask): void {
    const next = { ...settings.value.tasks }
    delete next[task]
    settings.value.tasks = next
    persist()
  }

  /** Copies one task's credentials to another (same provider, different role). */
  function copyTask(from: AiTask, to: AiTask): { ok: boolean; error?: string } {
    const config = configFor(from)
    if (!config) return { ok: false, error: '源任务尚未绑定' }
    return bindTask(to, { ...config })
  }

  async function test(task: AiTask, config?: AiConfig): Promise<AiTestResult | null> {
    const target = config ?? configFor(task)
    if (!target) {
      lastResult.value = {
        ok: false,
        format: 'openai',
        model: null,
        latency_ms: null,
        reply: null,
        error: '尚未填写配置',
        hint: '先填写 base_url、model 与 api_key',
      }
      return lastResult.value
    }
    testing.value = task
    try {
      const result = await testAiConnection(target)
      lastResult.value = result
      return result
    } catch (error) {
      lastResult.value = {
        ok: false,
        format: target.format,
        model: target.model,
        latency_ms: null,
        reply: null,
        error: (error as Error).message,
        hint: '本机 API 不可达，请确认后端已启动',
      }
      return lastResult.value
    } finally {
      testing.value = null
    }
  }

  function clearAll(): void {
    settings.value = emptyAiSettings()
    clearAiSettings()
    lastResult.value = null
  }

  function exportSettings(): string {
    return JSON.stringify(
      {
        schemaVersion: AI_SCHEMA_VERSION,
        updatedAt: settings.value.updatedAt,
        tasks: settings.value.tasks,
      },
      null,
      2,
    )
  }

  return {
    settings,
    testing,
    lastResult,
    boundTasks,
    hasChat,
    maskedKeys,
    reload,
    configFor,
    draftFor,
    bindTask,
    unbindTask,
    copyTask,
    test,
    clearAll,
    exportSettings,
  }
})
