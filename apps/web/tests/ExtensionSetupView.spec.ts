import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ExtensionSetupView from '@/views/ExtensionSetupView.vue'

const fetchMock = vi.fn()

vi.mock('vue-router', () => ({
  RouterLink: { template: '<a><slot /></a>' },
  useRouter: () => ({ push: vi.fn() }),
}))

function mountView() {
  return mount(ExtensionSetupView, {
    global: {
      plugins: [ElementPlus],
      stubs: { RouterLink: { template: '<a><slot /></a>' } },
    },
  })
}

describe('ExtensionSetupView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    delete (globalThis as { chrome?: unknown }).chrome
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('reports a healthy backend', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'ok', service: 'CareerPilot API' }),
    })

    const wrapper = mountView()
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/health'),
      expect.anything(),
    )
    expect(wrapper.find('.ext-status').text()).toContain('已连接')
    expect(wrapper.find('.ext-status').text()).toContain('CareerPilot API')
  })

  it('reports a down backend without throwing', async () => {
    fetchMock.mockRejectedValue(new Error('ECONNREFUSED'))

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('.ext-status').text()).toContain('未连接')
  })

  it('lists the install steps and the safety boundaries', async () => {
    fetchMock.mockResolvedValue({ ok: true, json: async () => ({ status: 'ok' }) })

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.findAll('.ext-steps li')).toHaveLength(4)
    expect(wrapper.text()).toContain('加载已解压的扩展程序')
    expect(wrapper.text()).toContain('永不自动点击提交按钮')
    expect(wrapper.text()).toContain('插件只是自动化到「填完」为止')
  })

  it('shows the current sync channel from the profile store', async () => {
    fetchMock.mockResolvedValue({ ok: true, json: async () => ({ status: 'ok' }) })

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('.ext-status').text()).toContain('③ 导出 JSON 粘贴')
  })
})
