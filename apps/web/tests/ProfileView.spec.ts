import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ProfileView from '@/views/ProfileView.vue'

vi.mock('@/api/resumes', () => ({
  listResumes: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 }),
  getResume: vi.fn(),
}))

vi.mock('vue-router', () => ({
  RouterLink: { template: '<a><slot /></a>' },
  useRouter: () => ({ push: vi.fn() }),
}))

function mountView() {
  return mount(ProfileView, {
    global: {
      plugins: [ElementPlus],
      stubs: { RouterLink: { template: '<a><slot /></a>' } },
    },
  })
}

describe('ProfileView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    delete (globalThis as { chrome?: unknown }).chrome
  })

  it('renders the local-only framing and every section', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('网申个人信息')
    expect(wrapper.text()).toContain('数据只存在这台电脑的浏览器里')
    for (const title of [
      '基本信息',
      '教育经历',
      '实习 / 工作经历',
      '项目经历',
      '技能与证书',
      '求职偏好',
      '链接',
    ]) {
      expect(wrapper.text()).toContain(title)
    }
  })

  it('shows channel ③ when no extension is reachable', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('.profile-sync').text()).toContain('③ 导出 JSON 粘贴')
  })

  it('writes basic fields into localStorage as the user types', async () => {
    const wrapper = mountView()
    await flushPromises()

    const nameInput = wrapper.find('.profile-form input')
    await nameInput.setValue('李四')
    await flushPromises()

    const raw = JSON.parse(localStorage.getItem('careerpilot.profile.v1') as string)
    expect(raw.basic.name).toBe('李四')
  })

  it('marks sensitive fields and keeps them out of the default export', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('身份证号（仅本地）')
    expect(wrapper.html()).toContain('默认不传输')
    expect(wrapper.text()).toContain('同步/导出时包含敏感字段')
  })

  it('adds an empty education row on demand', async () => {
    const wrapper = mountView()
    await flushPromises()

    const addButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('添加'))
    expect(addButton).toBeTruthy()
    await addButton?.trigger('click')
    await flushPromises()

    const raw = JSON.parse(localStorage.getItem('careerpilot.profile.v1') as string)
    expect(raw.education).toHaveLength(1)
  })
})
