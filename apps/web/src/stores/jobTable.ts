import { defineStore } from 'pinia'
import { ref } from 'vue'

import { getJobTablePreference, saveJobTablePreference } from '@/api/workspace'
import {
  DEFAULT_JOB_COLUMNS,
  JOB_COLUMN_LABELS,
} from '@/types/workspace'
import type { JobColumnOption } from '@/types/workspace'

const STORAGE_KEY = 'careerpilot.jobs.columns'

const ALL_COLUMNS: JobColumnOption[] = Object.keys(JOB_COLUMN_LABELS).map((key) => ({
  key,
  label: JOB_COLUMN_LABELS[key],
  default: DEFAULT_JOB_COLUMNS.includes(key),
}))

function sanitize(columns: string[]): string[] {
  const known = new Set(ALL_COLUMNS.map((column) => column.key))
  const ordered = ALL_COLUMNS.map((column) => column.key).filter(
    (key) => known.has(key) && columns.includes(key),
  )
  return ordered.length ? ordered : [...DEFAULT_JOB_COLUMNS]
}

function readLocal(): string[] | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? sanitize(parsed.map(String)) : null
  } catch {
    return null
  }
}

function writeLocal(columns: string[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(columns))
  } catch {
    /* storage unavailable — keep the in-memory state only */
  }
}

export const useJobTableStore = defineStore('jobTable', () => {
  const columns = ref<JobColumnOption[]>(ALL_COLUMNS)
  const visible = ref<string[]>(readLocal() ?? [...DEFAULT_JOB_COLUMNS])
  const loaded = ref(false)

  async function load(): Promise<void> {
    if (loaded.value) return
    try {
      const preference = await getJobTablePreference()
      columns.value = preference.available_columns
      visible.value = sanitize(preference.visible_columns)
      writeLocal(visible.value)
    } catch {
      /* offline or not signed in — the local copy stays authoritative */
    }
    loaded.value = true
  }

  async function setVisible(next: string[]): Promise<void> {
    visible.value = sanitize(next)
    writeLocal(visible.value)
    try {
      const preference = await saveJobTablePreference(visible.value)
      columns.value = preference.available_columns
    } catch {
      /* persisted locally; the server copy will catch up on the next save */
    }
  }

  return { columns, visible, loaded, load, setVisible }
})
