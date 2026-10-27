/**
 * Browser-local application profile store (plan §5.1 / §5.1.4).
 *
 * Storage: `localStorage['careerpilot.profile.v1']`. The plan mentions IndexedDB;
 * localStorage is used instead so the profile can be read synchronously while
 * building an autofill request and so the extension can read the slim snapshot
 * from the page (channel ②). See the deviation table in the refactor plan.
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import {
  EXTENSION_ID_KEY,
  PROFILE_SCHEMA_VERSION,
  PROFILE_STORAGE_KEY,
  PROFILE_SYNC_KEY,
  SENSITIVE_PATHS,
  emptyProfile,
  exportProfile,
  importProfile,
  toAutofillProfile,
  toSyncSnapshot,
} from '@/types/profile'
import type {
  CareerProfile,
  ProfileBasic,
  ProfileEducation,
  ProfileExperience,
  ProfileLinks,
  ProfilePreferences,
  ProfileProject,
  ProfileSkills,
  SyncChannel,
} from '@/types/profile'
import type { ResumeDetail } from '@/types/resumes'

interface ChromeRuntime {
  id?: string
  sendMessage?: (
    extensionId: string,
    message: unknown,
    callback?: (response: unknown) => void,
  ) => void
  lastError?: { message?: string }
}

function chromeRuntime(): ChromeRuntime | null {
  const chrome = (globalThis as { chrome?: { runtime?: ChromeRuntime } }).chrome
  return chrome?.runtime ?? null
}

function readLocal(): CareerProfile {
  try {
    const raw = localStorage.getItem(PROFILE_STORAGE_KEY)
    if (!raw) return emptyProfile()
    const result = importProfile(raw)
    if (!result.ok || !result.profile) return emptyProfile()
    return result.profile
  } catch {
    return emptyProfile()
  }
}

function writeLocal(profile: CareerProfile): void {
  try {
    localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profile))
  } catch {
    // Quota exceeded / private mode: the page shows a warning banner.
  }
}

export const useProfileStore = defineStore('profile', () => {
  const profile = ref<CareerProfile>(readLocal())
  const extensionId = ref<string>(localStorage.getItem(EXTENSION_ID_KEY) ?? '')
  const channel = ref<SyncChannel>('none')
  const lastSyncedAt = ref<string | null>(null)
  const syncMessage = ref<string>('')

  const confirmedPaths = computed(() => Object.keys(profile.value.confirmedAt))
  const filledCount = computed(() => {
    const basic = profile.value.basic
    return Object.values(basic).filter((value) => String(value ?? '').trim()).length
  })
  const isConfigured = computed(() => Boolean(profile.value.basic.name.trim()))

  function persist(): void {
    profile.value.profileVersion += 1
    profile.value.updatedAt = new Date().toISOString()
    writeLocal(profile.value)
  }

  function detectChannel(): SyncChannel {
    const runtime = chromeRuntime()
    const hasExtension = Boolean(runtime?.id) || Boolean(runtime?.sendMessage)
    if (hasExtension && extensionId.value.trim()) {
      channel.value = 'direct'
      return channel.value
    }
    const marked = document.documentElement.dataset.careerpilotExt
    if (marked) {
      channel.value = 'storage'
      return channel.value
    }
    // Extension reachable but no ID configured, or nothing detected at all:
    // both degrade to the manual JSON path.
    channel.value = 'json'
    return channel.value
  }

  function setExtensionId(value: string): void {
    extensionId.value = value.trim()
    try {
      localStorage.setItem(EXTENSION_ID_KEY, extensionId.value)
    } catch {
      // ignore
    }
    detectChannel()
  }

  function updateBasic(patch: Partial<ProfileBasic>, confirm = true): void {
    profile.value.basic = { ...profile.value.basic, ...patch }
    if (confirm) {
      const now = new Date().toISOString()
      for (const key of Object.keys(patch)) {
        profile.value.confirmedAt[`basic.${key}`] = now
      }
    }
    persist()
  }

  function updatePreferences(patch: Partial<ProfilePreferences>): void {
    profile.value.preferences = { ...profile.value.preferences, ...patch }
    persist()
  }

  function updateLinks(patch: Partial<ProfileLinks>): void {
    profile.value.links = { ...profile.value.links, ...patch }
    persist()
  }

  function updateSkills(patch: Partial<ProfileSkills>): void {
    profile.value.skills = { ...profile.value.skills, ...patch }
    persist()
  }

  function setEducation(rows: ProfileEducation[]): void {
    profile.value.education = rows
    persist()
  }

  function setExperience(rows: ProfileExperience[]): void {
    profile.value.experience = rows
    persist()
  }

  function setProjects(rows: ProfileProject[]): void {
    profile.value.projects = rows
    persist()
  }

  function confirmField(path: string): void {
    profile.value.confirmedAt[path] = new Date().toISOString()
    persist()
  }

  function isConfirmed(path: string): boolean {
    return Boolean(profile.value.confirmedAt[path])
  }

  /** Reads an existing resume and fills only the fields the user has not confirmed. */
  function prefillFromResume(resume: ResumeDetail): number {
    const head = resume.head
    const now = new Date().toISOString()
    const next: Partial<ProfileBasic> = {}
    const pairs: [keyof ProfileBasic, string | null][] = [
      ['name', head.name],
      ['phone', head.phone],
      ['email', head.email],
      ['city', head.city],
    ]
    for (const [key, value] of pairs) {
      if (!value) continue
      if (profile.value.basic[key].trim()) continue
      next[key] = value
      profile.value.confirmedAt[`basic.${key}`] = now
    }
    profile.value.basic = { ...profile.value.basic, ...next }

    const link = (label: string) =>
      head.links.find((item) => item.label.toLowerCase().includes(label))?.url ?? ''
    if (!profile.value.links.github && link('github')) {
      profile.value.links.github = link('github')
    }
    if (!profile.value.links.portfolio && (link('portfolio') || link('作品'))) {
      profile.value.links.portfolio = link('portfolio') || link('作品')
    }

    if (!profile.value.education.length) {
      const section = resume.sections.find((item) => item.key === 'education')
      profile.value.education = (section?.entries ?? []).map((entry) => ({
        id: entry.id,
        school: entry.title,
        major: entry.subtitle ?? '',
        degree: '',
        startDate: '',
        endDate: entry.period ?? '',
        gpa: '',
      }))
    }
    persist()
    return Object.keys(next).length
  }

  function clear(): void {
    profile.value = emptyProfile()
    writeLocal(profile.value)
    try {
      localStorage.removeItem(PROFILE_SYNC_KEY)
    } catch {
      // ignore
    }
    lastSyncedAt.value = null
    syncMessage.value = '已清空本地个人信息'
  }

  function toPayload(includeSensitive = false): Record<string, unknown> {
    return toAutofillProfile(profile.value, includeSensitive)
  }

  function exportJson(includeSensitive = false): string {
    return exportProfile(profile.value, { includeSensitive })
  }

  function importJson(raw: string): { ok: boolean; error?: string } {
    const result = importProfile(raw)
    if (!result.ok || !result.profile) {
      return { ok: false, error: result.error ?? '导入失败' }
    }
    profile.value = result.profile
    persist()
    return { ok: true }
  }

  /** Channel ②: write the slim snapshot the content script reads. */
  function writeSyncSnapshot(): void {
    try {
      localStorage.setItem(PROFILE_SYNC_KEY, JSON.stringify(toSyncSnapshot(profile.value)))
    } catch {
      // ignore
    }
  }

  /**
   * Channel ①: push to the extension over `chrome.runtime.sendMessage`.
   * Resolves with the ack payload, or rejects with a readable message.
   */
  async function pushToExtension(includeSensitive = false): Promise<string> {
    const runtime = chromeRuntime()
    if (!runtime?.sendMessage || !extensionId.value.trim()) {
      throw new Error('未安装扩展或未填写扩展 ID')
    }
    const message = {
      type: 'CAREERPILOT_PROFILE_SYNC',
      schemaVersion: PROFILE_SCHEMA_VERSION,
      profileVersion: profile.value.profileVersion,
      updatedAt: profile.value.updatedAt,
      fields: toAutofillProfile(profile.value, includeSensitive),
    }
    return await new Promise<string>((resolve, reject) => {
      runtime.sendMessage?.(extensionId.value.trim(), message, (response) => {
        const error = runtime.lastError
        if (error) {
          reject(new Error(error.message ?? '扩展未响应'))
          return
        }
        if (response && typeof response === 'object' && 'ok' in response) {
          const ack = response as { ok?: boolean; error?: string; profileVersion?: number }
          if (ack.ok === false) {
            reject(new Error(ack.error ?? '扩展拒绝了本次同步'))
            return
          }
          resolve(`扩展已接收（版本 ${ack.profileVersion ?? profile.value.profileVersion}）`)
          return
        }
        resolve('扩展已接收')
      })
    })
  }

  async function sync(includeSensitive = false): Promise<SyncChannel> {
    const active = detectChannel()
    syncMessage.value = ''
    if (active === 'direct') {
      try {
        syncMessage.value = await pushToExtension(includeSensitive)
        lastSyncedAt.value = new Date().toISOString()
        return 'direct'
      } catch (error) {
        syncMessage.value = `${(error as Error).message}；已回退到导出 JSON`
        channel.value = 'json'
        return 'json'
      }
    }
    if (active === 'storage') {
      writeSyncSnapshot()
      lastSyncedAt.value = new Date().toISOString()
      syncMessage.value = '已写入页面快照，扩展会在下次读取时获取'
      return 'storage'
    }
    syncMessage.value = '请使用下方「导出 JSON」并在插件弹窗中粘贴'
    return 'json'
  }

  return {
    profile,
    extensionId,
    channel,
    lastSyncedAt,
    syncMessage,
    confirmedPaths,
    filledCount,
    isConfigured,
    sensitivePaths: SENSITIVE_PATHS,
    detectChannel,
    setExtensionId,
    updateBasic,
    updatePreferences,
    updateLinks,
    updateSkills,
    setEducation,
    setExperience,
    setProjects,
    confirmField,
    isConfirmed,
    prefillFromResume,
    clear,
    toPayload,
    exportJson,
    importJson,
    writeSyncSnapshot,
    pushToExtension,
    sync,
  }
})
