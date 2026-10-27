import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import SettingsView from '@/views/SettingsView.vue'

const getAiMetrics = vi.fn()
const resetAiMetrics = vi.fn()

vi.mock('@/api/settings', () => ({
  getAiMetrics: (...args: unknown[]) => getAiMetrics(...args),
  resetAiMetrics: (...args: unknown[]) => resetAiMetrics(...args),
  testAiConnection: vi.fn(),
  sendAssistantMessage: vi.fn(),
}))

vi.mock('vue-router', () => ({
  RouterLink: { template: '<a><slot /></a>' },
  useRouter: () => ({ push: vi.fn() }),
}))

function mountView() {
  return mount(SettingsView, {
    global: {
      plugins: [ElementPlus],
      stubs: { RouterLink: { template: '<a><slot /></a>' } },
    },
  })
}

describe('SettingsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    getAiMetrics.mockReset().mockResolvedValue({
      calls: 4,
      failures: 1,
      average_latency_ms: 210.4,
      by_format: { openai: 3, anthropic: 1 },
    })
    resetAiMetrics.mockReset().mockResolvedValue(undefined)
  })

  it('lists the four bindable tasks and their fallback state', async () => {
    const wrapper = mountView()
    await flushPromises()

    const cards = wrapper.findAll('.settings-task')
    expect(cards).toHaveLength(4)
    expect(cards.map((card) => card.text())).toEqual([
      expect.stringContaining('对话'),
      expect.stringContaining('结构化抽取'),
      expect.stringContaining('向量化'),
      expect.stringContaining('重排'),
    ])
    expect(cards[0].text()).toContain('确定性')
  })

  it('persists general settings locally', async () => {
    const wrapper = mountView()
    await flushPromises()

    const timezoneSelect = wrapper.findAll('.settings-form .el-select')[0]
    expect(timezoneSelect.exists()).toBe(true)

    const radios = wrapper.findAll('.el-radio-button')
    expect(radios.length).toBe(2)
    expect(wrapper.text()).toContain('跟进提醒')

    const { usePreferencesStore } = await import('@/stores/preferences')
    usePreferencesStore().updateGeneral({ timezone: 'UTC', notifyChannel: 'email' })
    const raw = JSON.parse(localStorage.getItem('careerpilot.settings.v1') as string)
    expect(raw).toEqual({
      timezone: 'UTC',
      notifyChannel: 'email',
      remindersEnabled: true,
    })
  })

  it('shows the in-process call metrics without any prompt content', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('调用次数')
    expect(wrapper.text()).toContain('4')
    expect(wrapper.text()).toContain('210ms')
    expect(wrapper.text()).toContain('openai 3')
    // Metrics must never carry prompt text or credentials.
    expect(wrapper.text()).not.toContain('sk-')
  })

  it('documents the env fallback and the deterministic path', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('CAREERPILOT_AI_API_KEY')
    expect(wrapper.text()).toContain('回退到确定性实现')
  })

  it('warns that the exported config contains the key in clear text', async () => {
    const wrapper = mountView()
    await flushPromises()

    const { useAiConfigStore } = await import('@/stores/ai-config')
    const ai = useAiConfigStore()
    ai.bindTask('chat', {
      format: 'openai',
      baseUrl: 'https://api.test/v1',
      model: 'gpt-4o-mini',
      apiKey: 'sk-test',
      temperature: 0.2,
      maxTokens: 1024,
    })
    await flushPromises()

    expect(wrapper.findAll('.settings-task')[0].text()).toContain('已绑定')
    expect(ai.exportSettings()).toContain('sk-test')
  })
})
