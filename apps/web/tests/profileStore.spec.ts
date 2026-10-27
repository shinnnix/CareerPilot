import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  EXTENSION_ID_KEY,
  PROFILE_STORAGE_KEY,
  PROFILE_SYNC_KEY,
  SENSITIVE_PATHS,
  emptyProfile,
  exportProfile,
  importProfile,
  toAutofillProfile,
} from '@/types/profile'
import type { CareerProfile } from '@/types/profile'
import type { ResumeDetail } from '@/types/resumes'

const sendMessage = vi.fn()

function stubChrome() {
  ;(globalThis as { chrome?: unknown }).chrome = { runtime: { id: 'ext-1', sendMessage } }
}

function clearChrome() {
  delete (globalThis as { chrome?: unknown }).chrome
}

function makeProfile(): CareerProfile {
  const profile = emptyProfile()
  profile.basic.name = '李四'
  profile.basic.email = 'lisi@example.com'
  profile.basic.phone = '13900001111'
  profile.basic.idNumber = '310101200001011234'
  profile.basic.studentId = '2022001'
  profile.education = [
    {
      id: 'edu-1',
      school: '浙江大学',
      major: '软件工程',
      degree: '本科',
      startDate: '2022-09',
      endDate: '2026-06',
      gpa: '3.8',
    },
  ]
  return profile
}

async function store() {
  const { useProfileStore } = await import('@/stores/profile')
  return useProfileStore()
}

describe('profile types', () => {
  it('strips sensitive fields from the autofill payload by default', () => {
    const payload = toAutofillProfile(makeProfile()) as { basic: Record<string, unknown> }
    expect(payload.basic.email).toBe('lisi@example.com')
    expect(payload.basic.idNumber).toBeUndefined()
    expect(payload.basic.studentId).toBeUndefined()

    const withSensitive = toAutofillProfile(makeProfile(), true) as {
      basic: Record<string, unknown>
    }
    expect(withSensitive.basic.idNumber).toBe('310101200001011234')
  })

  it('exports without sensitive fields unless asked', () => {
    const profile = makeProfile()
    expect(exportProfile(profile)).not.toContain('310101200001011234')
    expect(exportProfile(profile, { includeSensitive: true })).toContain('310101200001011234')
  })

  it('round-trips through importProfile', () => {
    const result = importProfile(exportProfile(makeProfile()))
    expect(result.ok).toBe(true)
    expect(result.profile?.basic.name).toBe('李四')
    expect(result.profile?.education[0].school).toBe('浙江大学')
  })

  it('rejects unknown schema versions and broken JSON', () => {
    expect(importProfile('not json').ok).toBe(false)
    expect(importProfile('{"schemaVersion":99}').ok).toBe(false)
  })

  it('accepts a plugin payload that nests fields', () => {
    const result = importProfile(
      JSON.stringify({ schemaVersion: 1, profileVersion: 3, fields: { basic: { name: '王五' } } }),
    )
    expect(result.ok).toBe(true)
    expect(result.profile?.basic.name).toBe('王五')
    expect(result.profile?.profileVersion).toBe(3)
  })

  it('exposes the sensitive paths list', () => {
    expect(SENSITIVE_PATHS).toEqual(['basic.idNumber', 'basic.studentId'])
  })
})

describe('profile store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    sendMessage.mockReset()
    clearChrome()
  })

  it('persists basic fields and stamps confirmedAt', async () => {
    const profile = await store()
    profile.updateBasic({ name: '李四', email: 'lisi@example.com' })

    expect(profile.profile.basic.name).toBe('李四')
    expect(profile.isConfirmed('basic.name')).toBe(true)
    const raw = JSON.parse(localStorage.getItem(PROFILE_STORAGE_KEY) as string)
    expect(raw.basic.email).toBe('lisi@example.com')
  })

  it('does not confirm sensitive fields edited without confirmation', async () => {
    const profile = await store()
    profile.updateBasic({ idNumber: '310101200001011234' }, false)

    expect(profile.profile.basic.idNumber).toBe('310101200001011234')
    expect(profile.isConfirmed('basic.idNumber')).toBe(false)
  })

  it('prefills from a resume without overwriting existing values', async () => {
    const profile = await store()
    profile.updateBasic({ name: '李四' })

    const resume = {
      head: {
        name: '张三',
        phone: '13800000000',
        email: 'zhangsan@example.com',
        city: '上海',
        links: [{ label: 'GitHub', url: 'https://github.com/zhangsan' }],
      },
      sections: [
        {
          id: 'sec-1',
          key: 'education',
          title: '教育经历',
          entries: [
            { id: 'e1', title: '浙江大学', subtitle: '软件工程', period: '2022-2026', bullets: [] },
          ],
        },
      ],
    } as unknown as ResumeDetail

    const filled = profile.prefillFromResume(resume)

    expect(profile.profile.basic.name).toBe('李四')
    expect(profile.profile.basic.email).toBe('zhangsan@example.com')
    expect(profile.profile.links.github).toBe('https://github.com/zhangsan')
    expect(profile.profile.education[0].school).toBe('浙江大学')
    expect(filled).toBe(3)
  })

  it('detects channel ① only when an extension id is configured', async () => {
    stubChrome()
    const profile = await store()

    expect(profile.detectChannel()).toBe('json')
    profile.setExtensionId('abcdefghijklmnop')
    expect(profile.detectChannel()).toBe('direct')
    expect(localStorage.getItem(EXTENSION_ID_KEY)).toBe('abcdefghijklmnop')
  })

  it('falls back to channel ② when the content script marked the page', async () => {
    document.documentElement.dataset.careerpilotExt = '1'
    const profile = await store()
    try {
      expect(profile.detectChannel()).toBe('storage')
    } finally {
      delete document.documentElement.dataset.careerpilotExt
    }
  })

  it('pushes the profile over chrome.runtime.sendMessage and records the ack', async () => {
    stubChrome()
    const profile = await store()
    profile.setExtensionId('ext-1')
    profile.updateBasic({ name: '李四' })
    sendMessage.mockImplementation((_id, _message, callback) => {
      callback({ ok: true, profileVersion: 2 })
    })

    const used = await profile.sync()

    expect(used).toBe('direct')
    expect(sendMessage).toHaveBeenCalledTimes(1)
    const [, message] = sendMessage.mock.calls[0]
    expect(message.type).toBe('CAREERPILOT_PROFILE_SYNC')
    expect(message.fields.basic.name).toBe('李四')
    expect(profile.lastSyncedAt).toBeTruthy()
  })

  it('degrades to JSON when the extension reports an error', async () => {
    stubChrome()
    const profile = await store()
    profile.setExtensionId('ext-1')
    sendMessage.mockImplementation((_id, _message, callback) => {
      callback({ ok: false, error: '拒绝' })
    })

    const used = await profile.sync()

    expect(used).toBe('json')
    expect(profile.syncMessage).toContain('拒绝')
  })

  it('writes a sensitive-free snapshot for channel ②', async () => {
    const profile = await store()
    profile.importJson(exportProfile(makeProfile(), { includeSensitive: true }))
    profile.writeSyncSnapshot()

    const snapshot = JSON.parse(localStorage.getItem(PROFILE_SYNC_KEY) as string)
    expect(snapshot.fields.basic.name).toBe('李四')
    expect(snapshot.fields.basic.idNumber).toBeUndefined()
    expect(snapshot.source).toBe('page')
  })

  it('clears everything on request', async () => {
    const profile = await store()
    profile.updateBasic({ name: '李四' })
    profile.clear()

    expect(profile.profile.basic.name).toBe('')
    expect(localStorage.getItem(PROFILE_SYNC_KEY)).toBeNull()
  })
})
