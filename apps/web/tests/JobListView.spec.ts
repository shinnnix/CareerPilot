import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import JobListView from '@/views/JobListView.vue'

const listJobCatalog = vi.fn()
const getJobFacets = vi.fn()
const getJobAnnouncement = vi.fn()
const markJob = vi.fn()
const saveJobTablePreference = vi.fn()
const getJobTablePreference = vi.fn()

vi.mock('@/api/workspace', () => ({
  listJobCatalog: (...args: unknown[]) => listJobCatalog(...args),
  getJobFacets: (...args: unknown[]) => getJobFacets(...args),
  getJobAnnouncement: (...args: unknown[]) => getJobAnnouncement(...args),
  markJob: (...args: unknown[]) => markJob(...args),
  getJobTablePreference: (...args: unknown[]) => getJobTablePreference(...args),
  saveJobTablePreference: (...args: unknown[]) => saveJobTablePreference(...args),
  downloadJobCatalogCsv: async () => new Blob([], { type: 'text/csv' }),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, params: {} }),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  RouterLink: { template: '<a><slot /></a>' },
}))

const row = {
  id: 'ann-1',
  title: '星河智能2027届校园招聘公告',
  company: { name: '星河智能', type: '民企', scale: '1000-5000人', industry: '人工智能' },
  recruitment_type: '秋招',
  target_cohort: '2027届',
  locations: ['上海', '深圳'],
  positions_preview: '后端开发工程师、算法工程师',
  position_count: 2,
  published_at: '2026-09-01',
  updated_at: '2026-09-18T10:00:00+00:00',
  deadline: { text: '2026-11-30', at: '2026-11-30' },
  mark_status: 'applied',
  mark_status_label: '已投递',
  mark_note: null,
  stage_summary: { 已投递: 1 },
  application_ids: ['app-1'],
  applied_position_count: 1,
  source: { kind: 'manual', name: null, url: null },
}

function mountView() {
  return mount(JobListView, {
    global: {
      plugins: [ElementPlus, createPinia()],
      stubs: {
        ImportJobDialog: true,
        ApplicationFormDialog: true,
        RouterLink: { template: '<a><slot /></a>' },
      },
    },
  })
}

describe('JobListView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    listJobCatalog.mockReset().mockResolvedValue({
      items: [row],
      page: 1,
      page_size: 20,
      total: 1,
      page_count: 1,
    })
    getJobFacets.mockReset().mockResolvedValue({
      company_types: [{ value: '民企', label: '民企', count: 1 }],
      recruitment_types: [{ value: '秋招', label: '秋招', count: 1 }],
      target_cohorts: [{ value: '2027届', label: '2027届', count: 1 }],
      locations: [{ value: '上海', label: '上海', count: 1 }],
      job_categories: [],
      statuses: [{ value: 'applied', label: '已投递', count: 1 }],
    })
    getJobTablePreference.mockReset().mockResolvedValue({
      table_key: 'jobs',
      visible_columns: ['company_name', 'positions', 'mark_status'],
      available_columns: [
        { key: 'company_name', label: '公司名称', default: true },
        { key: 'positions', label: '岗位', default: true },
        { key: 'mark_status', label: '状态', default: true },
      ],
    })
    saveJobTablePreference.mockReset()
  })

  it('渲染页头、数据条与公告行', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('发现适合你的下一站')
    expect(wrapper.text()).toContain('1 条职位')
    expect(wrapper.text()).toContain('星河智能')
    expect(wrapper.text()).toContain('已投递')
    expect(wrapper.text()).toContain('1/2 个岗位已投递')
    expect(listJobCatalog).toHaveBeenCalledTimes(1)
  })

  it('只渲染列设置中可见的列', async () => {
    const wrapper = mountView()
    await flushPromises()

    const headers = wrapper.findAll('.el-table__header th').map((th) => th.text())
    expect(headers).toContain('公司名称')
    expect(headers).toContain('岗位')
    expect(headers).not.toContain('招聘类型')
    expect(headers).not.toContain('投递截止')
  })

  it('接口失败时展示错误态与重试按钮', async () => {
    listJobCatalog.mockRejectedValueOnce(new Error('boom'))
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('boom')
    expect(wrapper.text()).toContain('重新加载')
  })

  it('没有数据时展示空态', async () => {
    listJobCatalog.mockResolvedValueOnce({
      items: [],
      page: 1,
      page_size: 20,
      total: 0,
      page_count: 1,
    })
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('还没有符合条件的职位')
  })
})
