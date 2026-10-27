import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'

import WorkspaceSidebar from '@/components/WorkspaceSidebar.vue'
import {
  SIDEBAR_STORAGE_KEY,
  readSidebarCollapsed,
  writeSidebarCollapsed,
} from '@/composables/useSidebarCollapse'

const RouterLinkStub = {
  props: ['to'],
  template: '<a class="router-link" :href="to"><slot /></a>',
}

function mountSidebar(props: Record<string, unknown> = {}) {
  return mount(WorkspaceSidebar, {
    props,
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
        'el-icon': { template: '<span class="icon"><slot /></span>' },
      },
    },
  })
}

describe('WorkspaceSidebar', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('渲染两个分组与三个工作空间入口', () => {
    const wrapper = mountSidebar()

    const labels = wrapper.findAll('.sidebar-group-label').map((node) => node.text())
    expect(labels).toEqual(['工作空间', '更多工具'])

    const workspaceLinks = wrapper.findAll('.sidebar-group')[0].findAll('a.sidebar-item')
    expect(workspaceLinks.map((node) => node.text())).toEqual(['职位信息', '投递记录', '我的简历'])
    expect(workspaceLinks.map((node) => node.attributes('href'))).toEqual([
      '/workspace/jobs',
      '/workspace/applications',
      '/workspace/resumes',
    ])
  })

  it('更多工具下的六个入口都已上线可点击', () => {
    const wrapper = mountSidebar()
    const moreTools = wrapper.findAll('.sidebar-group')[1]

    const links = moreTools.findAll('a.sidebar-item')
    expect(links.map((node) => node.text())).toEqual([
      '网申个人信息',
      '网申填写插件',
      '资料库',
      '证据检索',
      '求职 Agent',
      'AI 与设置',
    ])
    expect(links.map((node) => node.attributes('href'))).toEqual([
      '/workspace/profile',
      '/workspace/extension',
      '/workspace/library',
      '/workspace/evidence',
      '/workspace/assistant',
      '/workspace/settings',
    ])
    expect(moreTools.findAll('.sidebar-item--disabled')).toHaveLength(0)
    expect(moreTools.findAll('.sidebar-item-tag')).toHaveLength(0)
  })

  it('折叠时隐藏文案与折叠按钮的图标方向可切换', async () => {
    const wrapper = mountSidebar({ collapsed: true })

    expect(wrapper.findAll('.workspace-sidebar-toggle')).toHaveLength(1)
    await wrapper.find('.workspace-sidebar-toggle').trigger('click')

    expect(wrapper.emitted('toggle-collapse')).toHaveLength(1)
  })

  it('窄屏不渲染折叠按钮（用抽屉代替）', () => {
    const wrapper = mountSidebar({ narrow: true })

    expect(wrapper.find('.workspace-sidebar-toggle').exists()).toBe(false)
  })

  it('折叠状态持久化到 localStorage', () => {
    expect(readSidebarCollapsed()).toBe(false)

    writeSidebarCollapsed(true)
    expect(localStorage.getItem(SIDEBAR_STORAGE_KEY)).toBe('1')
    expect(readSidebarCollapsed()).toBe(true)

    writeSidebarCollapsed(false)
    expect(readSidebarCollapsed()).toBe(false)
  })
})
