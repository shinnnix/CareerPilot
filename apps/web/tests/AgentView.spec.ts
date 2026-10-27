import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AgentView from '@/views/AgentView.vue'

const sendAssistantMessage = vi.fn()

vi.mock('@/api/agent', () => ({
  createAgentRun: vi.fn(),
  confirmAgentRun: vi.fn(),
  resumeAgentRun: vi.fn(),
  subscribeAgentEvents: vi.fn(() => ({ close: vi.fn() })),
}))

vi.mock('@/api/applications', () => ({
  listApplications: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 }),
}))

vi.mock('@/api/documents', () => ({
  listDocuments: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 }),
}))

vi.mock('@/api/jobs', () => ({
  listJobs: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 }),
}))

vi.mock('@/api/settings', () => ({
  sendAssistantMessage: (...args: unknown[]) => sendAssistantMessage(...args),
  testAiConnection: vi.fn(),
  getAiMetrics: vi.fn(),
  resetAiMetrics: vi.fn(),
}))

vi.mock('vue-router', () => ({
  RouterLink: { template: '<a><slot /></a>' },
  useRouter: () => ({ push: vi.fn() }),
}))

function mountView() {
  return mount(AgentView, {
    global: {
      plugins: [ElementPlus],
      stubs: { RouterLink: { template: '<a><slot /></a>' } },
    },
  })
}

describe('AgentView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    sendAssistantMessage.mockReset()
  })

  it('reframes the page as a job-search assistant', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('求职助手')
    expect(wrapper.text()).toContain('只读动作直接执行')
    expect(wrapper.text()).not.toContain('LANGGRAPH WORKFLOW')
  })

  it('blocks chat and points to settings when no model is bound', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('还没有配置对话模型')
    expect(wrapper.find('.agent-chat textarea').attributes('disabled')).toBeDefined()

    const sendButton = wrapper
      .findAll('.agent-chat button')
      .find((node) => node.text().includes('发送'))
    expect(sendButton?.attributes('disabled')).toBeDefined()
  })

  it('enables chat once a chat config is bound and sends the message', async () => {
    const { useAiConfigStore } = await import('@/stores/ai-config')
    useAiConfigStore().bindTask('chat', {
      format: 'openai',
      baseUrl: 'https://api.test/v1',
      model: 'gpt-4o-mini',
      apiKey: 'sk-test',
      temperature: 0.2,
      maxTokens: 1024,
    })
    sendAssistantMessage.mockResolvedValue({
      reply: '先跟进最近投递的两家。',
      format: 'openai',
      model: 'gpt-4o-mini',
      latency_ms: 120,
    })

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).not.toContain('还没有配置对话模型')
    expect(wrapper.text()).toContain('已绑定 · gpt-4o-mini')

    await wrapper.find('.agent-chat textarea').setValue('这周先跟进哪些投递？')
    await wrapper
      .findAll('.agent-chat button')
      .find((node) => node.text().includes('发送'))
      ?.trigger('click')
    await flushPromises()

    expect(sendAssistantMessage).toHaveBeenCalledTimes(1)
    expect(sendAssistantMessage.mock.calls[0][0]).toBe('这周先跟进哪些投递？')
    expect(wrapper.text()).toContain('先跟进最近投递的两家。')
  })

  it('surfaces the 409 hint instead of inventing an answer', async () => {
    const { useAiConfigStore } = await import('@/stores/ai-config')
    useAiConfigStore().bindTask('chat', {
      format: 'openai',
      baseUrl: 'https://api.test/v1',
      model: 'gpt-4o-mini',
      apiKey: 'sk-test',
      temperature: 0.2,
      maxTokens: 1024,
    })
    sendAssistantMessage.mockRejectedValue(new Error('尚未配置 AI 凭据，无法进行对话'))

    const wrapper = mountView()
    await flushPromises()

    await wrapper.find('.agent-chat textarea').setValue('你好')
    await wrapper
      .findAll('.agent-chat button')
      .find((node) => node.text().includes('发送'))
      ?.trigger('click')
    await flushPromises()

    expect(wrapper.find('.agent-chat-error').text()).toContain('尚未配置 AI 凭据')
  })
})
