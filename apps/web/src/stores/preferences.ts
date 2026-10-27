import { defineStore } from 'pinia'
import { ref } from 'vue'

const GENERAL_KEY = 'careerpilot.settings.v1'

export type NotifyChannel = 'in_app' | 'email'

export interface GeneralSettings {
  timezone: string
  notifyChannel: NotifyChannel
  remindersEnabled: boolean
}

function readGeneral(): GeneralSettings {
  const fallback: GeneralSettings = {
    timezone: 'Asia/Shanghai',
    notifyChannel: 'in_app',
    remindersEnabled: true,
  }
  try {
    const raw = localStorage.getItem(GENERAL_KEY)
    if (!raw) return fallback
    const parsed = JSON.parse(raw) as Partial<GeneralSettings>
    return {
      timezone: parsed.timezone || fallback.timezone,
      notifyChannel: parsed.notifyChannel === 'email' ? 'email' : 'in_app',
      remindersEnabled: parsed.remindersEnabled ?? fallback.remindersEnabled,
    }
  } catch {
    return fallback
  }
}

export const usePreferencesStore = defineStore('preferences', () => {
  const pageSize = ref(9)
  const general = ref<GeneralSettings>(readGeneral())

  function setPageSize(value: number) {
    pageSize.value = value
  }

  function updateGeneral(patch: Partial<GeneralSettings>): void {
    general.value = { ...general.value, ...patch }
    try {
      localStorage.setItem(GENERAL_KEY, JSON.stringify(general.value))
    } catch {
      // Storage disabled: keep the in-memory value for this session.
    }
  }

  return { pageSize, setPageSize, general, updateGeneral }
})
