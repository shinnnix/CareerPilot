import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  AI_CONFIG_HEADER,
  AI_STORAGE_KEY,
  encodeAiConfigHeader,
  emptyAiConfig,
  isValidAiConfig,
  maskApiKey,
  taskSupportsFormat,
  toWireConfig,
} from '@/types/ai'
import type { AiConfig } from '@/types/ai'

const testAiConnection = vi.fn()

vi.mock('@/api/settings', () => ({
  testAiConnection: (...args: unknown[]) => testAiConnection(...args),
  sendAssistantMessage: vi.fn(),
}))

function decodeHeader(header: string): Record<string, unknown> {
  const padded = header.replace(/-/g, '+').replace(/_/g, '/')
  const json = decodeURIComponent(
    atob(padded + '='.repeat((4 - (padded.length % 4)) % 4))
      .split('')
      .map((char) => `%${char.charCodeAt(0).toString(16).padStart(2, '0')}`)
      .join(''),
  )
  return JSON.parse(json) as Record<string, unknown>
}

function config(overrides: Partial<AiConfig> = {}): AiConfig {
  return { ...emptyAiConfig('openai'), apiKey: 'sk-test', ...overrides }
}

async function store() {
  const { useAiConfigStore } = await import('@/stores/ai-config')
  return useAiConfigStore()
}

describe('ai config wire format', () => {
  it('encodes base64url JSON with snake_case keys', () => {
    const header = encodeAiConfigHeader(config({ baseUrl: 'https://api.test/v1/' }))
    expect(header).not.toContain('=')
    expect(header).not.toContain('+')
    expect(header).not.toContain('/')

    const decoded = decodeHeader(header)
    expect(decoded.format).toBe('openai')
    expect(decoded.base_url).toBe('https://api.test/v1')
    expect(decoded.api_key).toBe('sk-test')
    expect(decoded.max_tokens).toBe(1024)
  })

  it('survives non-ASCII model names', () => {
    const decoded = decodeHeader(encodeAiConfigHeader(config({ model: '模型-中文' })))
    expect(decoded.model).toBe('模型-中文')
  })

  it('trims trailing slashes in the wire payload', () => {
    expect(toWireConfig(config({ baseUrl: ' https://x.test/v1/// ' })).base_url).toBe(
      'https://x.test/v1',
    )
  })

  it('treats anthropic as unsupported for embedding and rerank', () => {
    expect(taskSupportsFormat('chat', 'anthropic')).toBe(true)
    expect(taskSupportsFormat('extraction', 'anthropic')).toBe(true)
    expect(taskSupportsFormat('embedding', 'anthropic')).toBe(false)
    expect(taskSupportsFormat('rerank', 'anthropic')).toBe(false)
  })

  it('masks api keys', () => {
    expect(maskApiKey('')).toBe('未填写')
    expect(maskApiKey('sk-1234567890abcd')).toBe('sk-1****abcd')
  })

  it('validates required fields', () => {
    expect(isValidAiConfig(config())).toBe(true)
    expect(isValidAiConfig(config({ apiKey: '  ' }))).toBe(false)
    expect(isValidAiConfig(null)).toBe(false)
  })

  it('exposes the header name the backend expects', () => {
    expect(AI_CONFIG_HEADER).toBe('X-AI-Config')
  })
})

describe('ai config store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    testAiConnection.mockReset()
  })

  it('binds a task and persists it locally', async () => {
    const ai = await store()
    const result = ai.bindTask('chat', config({ model: 'deepseek-chat' }))

    expect(result.ok).toBe(true)
    expect(ai.hasChat).toBe(true)
    expect(ai.configFor('chat')?.model).toBe('deepseek-chat')
    const raw = JSON.parse(localStorage.getItem(AI_STORAGE_KEY) as string)
    expect(raw.tasks.chat.apiKey).toBe('sk-test')
  })

  it('refuses anthropic for embedding and rerank', async () => {
    const ai = await store()
    const result = ai.bindTask('embedding', config({ format: 'anthropic' }))

    expect(result.ok).toBe(false)
    expect(result.error).toContain('Anthropic')
    expect(ai.configFor('embedding')).toBeNull()
  })

  it('refuses an incomplete config', async () => {
    const ai = await store()
    const result = ai.bindTask('chat', config({ apiKey: '' }))

    expect(result.ok).toBe(false)
    expect(result.error).toContain('api_key')
  })

  it('unbinds and falls back to the deterministic path', async () => {
    const ai = await store()
    ai.bindTask('chat', config())
    ai.unbindTask('chat')

    expect(ai.hasChat).toBe(false)
    expect(ai.boundTasks).toEqual([])
  })

  it('copies credentials between tasks', async () => {
    const ai = await store()
    ai.bindTask('chat', config({ model: 'gpt-4o-mini' }))
    const result = ai.copyTask('chat', 'extraction')

    expect(result.ok).toBe(true)
    expect(ai.configFor('extraction')?.model).toBe('gpt-4o-mini')
    expect(ai.boundTasks).toEqual(['chat', 'extraction'])
  })

  it('records a failed test with the backend hint', async () => {
    const ai = await store()
    ai.bindTask('chat', config())
    testAiConnection.mockResolvedValue({
      ok: false,
      format: 'openai',
      model: 'gpt-4o-mini',
      latency_ms: 12,
      reply: null,
      error: 'HTTP 401: invalid api key',
      hint: '凭据被拒绝：检查 api_key 是否有效、是否与所选格式匹配',
    })

    const result = await ai.test('chat')

    expect(result?.ok).toBe(false)
    expect(ai.lastResult?.hint).toContain('凭据被拒绝')
  })

  it('reports a missing config without calling the API', async () => {
    const ai = await store()
    const result = await ai.test('chat')

    expect(result?.ok).toBe(false)
    expect(testAiConnection).not.toHaveBeenCalled()
  })

  it('clears all local settings', async () => {
    const ai = await store()
    ai.bindTask('chat', config())
    ai.clearAll()

    expect(ai.boundTasks).toEqual([])
    expect(localStorage.getItem(AI_STORAGE_KEY)).toBeNull()
  })

  it('exports settings as JSON', async () => {
    const ai = await store()
    ai.bindTask('chat', config())
    const exported = JSON.parse(ai.exportSettings()) as { tasks: Record<string, unknown> }

    expect(Object.keys(exported.tasks)).toEqual(['chat'])
  })
})
