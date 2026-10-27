import ElementPlus from 'element-plus'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it } from 'vitest'
import { defineComponent } from 'vue'

import WorkspaceLayout from '@/layouts/WorkspaceLayout.vue'

const StubView = defineComponent({ template: '<div class="stub-view">stub</div>' })
const RootView = defineComponent({ template: '<RouterView />' })

function buildRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/workspace',
        component: WorkspaceLayout,
        children: [
          { path: '', redirect: '/workspace/resumes' },
          {
            path: 'resumes',
            name: 'resumes',
            component: StubView,
            meta: { group: '工作空间', title: '我的简历' },
          },
        ],
      },
      { path: '/login', name: 'login', component: StubView, meta: { public: true } },
      { path: '/:pathMatch(.*)*', component: StubView },
    ],
  })
}

async function mountAt(path: string) {
  const router = buildRouter()
  await router.push(path)
  await router.isReady()
  const wrapper = mount(RootView, { global: { plugins: [router, ElementPlus] } })
  await router.isReady()
  return wrapper
}

describe('WorkspaceLayout', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('渲染侧栏、面包屑与内容区', async () => {
    const wrapper = await mountAt('/workspace/resumes')

    expect(wrapper.find('.workspace-sidebar').exists()).toBe(true)
    expect(wrapper.find('.workspace-content').exists()).toBe(true)
    expect(wrapper.find('.stub-view').exists()).toBe(true)

    const breadcrumb = wrapper.find('.workspace-breadcrumb').text()
    expect(breadcrumb).toContain('工作空间')
    expect(breadcrumb).toContain('我的简历')
  })

  it('折叠侧栏后写入 localStorage 并加上折叠样式', async () => {
    const wrapper = await mountAt('/workspace/resumes')

    expect(wrapper.find('.workspace-shell--collapsed').exists()).toBe(false)
    await wrapper.find('.workspace-sidebar-toggle').trigger('click')

    expect(localStorage.getItem('careerpilot.sidebar.collapsed')).toBe('1')
    expect(wrapper.find('.workspace-shell--collapsed').exists()).toBe(true)
  })
})
