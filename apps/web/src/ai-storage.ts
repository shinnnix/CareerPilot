/**
 * Low-level access to the browser-local AI settings (plan §5.3).
 *
 * Kept separate from the Pinia store so the axios interceptor can read the
 * header value without importing a store (which would create a cycle).
 */

import {
  AI_CONFIG_HEADER,
  AI_SCHEMA_VERSION,
  AI_STORAGE_KEY,
  encodeAiConfigHeader,
  emptyAiSettings,
  isValidAiConfig,
} from '@/types/ai'
import type { AiConfig, AiSettings, AiTask } from '@/types/ai'

export function readAiSettings(): AiSettings {
  try {
    const raw = localStorage.getItem(AI_STORAGE_KEY)
    if (!raw) return emptyAiSettings()
    const parsed = JSON.parse(raw) as Partial<AiSettings>
    if (!parsed || typeof parsed !== 'object') return emptyAiSettings()
    if (Number(parsed.schemaVersion ?? AI_SCHEMA_VERSION) > AI_SCHEMA_VERSION) {
      return emptyAiSettings()
    }
    const tasks: Partial<Record<AiTask, AiConfig>> = {}
    for (const [key, value] of Object.entries(parsed.tasks ?? {})) {
      const config = value as AiConfig
      if (isValidAiConfig(config)) tasks[key as AiTask] = config
    }
    return {
      schemaVersion: AI_SCHEMA_VERSION,
      updatedAt: parsed.updatedAt ?? new Date().toISOString(),
      tasks,
    }
  } catch {
    return emptyAiSettings()
  }
}

export function writeAiSettings(settings: AiSettings): void {
  try {
    localStorage.setItem(AI_STORAGE_KEY, JSON.stringify(settings))
  } catch {
    // Storage full or disabled: the settings page surfaces this separately.
  }
}

export function clearAiSettings(): void {
  try {
    localStorage.removeItem(AI_STORAGE_KEY)
  } catch {
    // ignore
  }
}

/** Config bound to `task`, falling back to the first bound task. */
export function resolveAiConfig(task: AiTask, settings?: AiSettings): AiConfig | null {
  const current = settings ?? readAiSettings()
  const bound = current.tasks[task]
  if (isValidAiConfig(bound)) return bound as AiConfig
  return null
}

export function aiConfigHeader(task: AiTask, settings?: AiSettings): string | null {
  const config = resolveAiConfig(task, settings)
  return config ? encodeAiConfigHeader(config) : null
}

export { AI_CONFIG_HEADER }
