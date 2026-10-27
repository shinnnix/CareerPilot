import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ApplicationsView from '@/views/ApplicationsView.vue'

const listApplicationRecords = vi.fn()
const getApplicationMetrics = vi.fn()
const updateApplicationRecord = vi.fn()
const deleteApplicationRecord = vi.fn()

vi.mock('@/api/workspace', () => ({
  listApplicationRecords: (...args: unknown[]) => listApplicationRecords(...args),
  getApplicationMetrics: (...args: unknown[]) => getApplicationMetrics(...args),
  updateApplicationRecord: (...args: unknown[]) => updateApplicationRecord(...args),
  deleteApplicationRecord: (...args: unknown[]) => deleteApplicationRecord(...args),
  downloadApplicationCsv: async () => new Blob([], { type: 'text/csv' }),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, params: {} }),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  RouterLink: { template: '<a><slot /></a>' },
}))

const row = {
  id: 'app-1',
  company_name: '星河智能',
  position_title: '后端开发工程师',
  status: 'applied',
  status_label: '已投递',
  is_terminal: false,
  applied_at: '2026-03-02T09:00:00+00:00',
  follow_up_at: '2026-03-20T00:00:00+00:00',
  follow_up_due: false,
  channel: '官网',
  contact_name: '王老师',
  contact_info: 'wang@example.com',
  link: null,
  notes: null,
  closed_reason: null,
  rejected_stage: null,
  announcement_id: 'ann-1',
  position_id: 'pos-1',
  job_id: null,
  row_version: 1,
  created_at: '2026-03-02T09:00:00+00:00',
  updated_at: '2026-03-02T09:00:00+00:00',
}

function mountView() {
  return mount(ApplicationsView, {
    global: {
      plugins: [ElementPlus],
      stubs: {
        ApplicationManualDialog: true,
        RouterLink: { template: '<a><slot /></a>' },
      },
    },
  })
}

describe('ApplicationsView', () => {
  beforeEach(() => {
    listApplicationRecords.mockReset().mockResolvedValue({
      items: [row],
      page: 1,
      page_size: 20,
      total: 1,
      page_count: 1,
      status_counts: { applied: 1 },
    })
    getApplicationMetrics.mockReset().mockResolvedValue({
      total: 1,
      by_status: { applied: 1 },
      due_follow_ups: 0,
      terminal: 0,
      active: 1,
    })
    updateApplicationRecord.mockReset()
    deleteApplicationRecord.mockReset()
  })

  it('渲染页头、数据条与八列', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('每一份投递，都有进展')
    expect(wrapper.text()).toContain('1 条投递')
    expect(wrapper.text()).toContain('星河智能')
    expect(wrapper.text()).toContain('后端开发工程师')
    expect(wrapper.text()).toContain('已投递')
    expect(wrapper.text()).toContain('官网')
    expect(wrapper.text()).toContain('王老师')

    const headers = wrapper.findAll('.el-table__header th').map((th) => th.text())
    expect(headers).toEqual(
      expect.arrayContaining([
        '公司',
        '岗位',
        '状态',
        '投递日期',
        '跟进日期',
        '渠道',
        '联系人',
        '操作',
      ]),
    )
    expect(listApplicationRecords).toHaveBeenCalledTimes(1)
  })

  it('状态集合里没有「正在面试」', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).not.toContain('面试中')
    expect(wrapper.text()).not.toContain('准备中')
  })

  it('终态行降饱和，到期跟进高亮', async () => {
    listApplicationRecords.mockResolvedValueOnce({
      items: [
        { ...row, id: 'app-2', status: 'rejected', status_label: '已挂', is_terminal: true },
        { ...row, id: 'app-3', follow_up_due: true },
      ],
      page: 1,
      page_size: 20,
      total: 2,
      page_count: 1,
      status_counts: { rejected: 1, applied: 1 },
    })
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.findAll('tr.row-terminal').length).toBeGreaterThanOrEqual(1)
    expect(wrapper.findAll('.is-urgent').length).toBeGreaterThanOrEqual(1)
  })

  it('没有数据时展示空态与引导', async () => {
    listApplicationRecords.mockResolvedValueOnce({
      items: [],
      page: 1,
      page_size: 20,
      total: 0,
      page_count: 1,
      status_counts: {},
    })
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('还没有投递记录')
    expect(wrapper.text()).toContain('去职位信息')
  })

  it('接口失败时展示错误态', async () => {
    listApplicationRecords.mockRejectedValueOnce(new Error('boom'))
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('boom')
    expect(wrapper.text()).toContain('重新加载')
  })
})
