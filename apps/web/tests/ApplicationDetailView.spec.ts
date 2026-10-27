import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ApplicationDetailView from '@/views/ApplicationDetailView.vue'

const getApplicationRecord = vi.fn()
const updateApplicationRecord = vi.fn()
const saveStageDetail = vi.fn()
const deleteStageDetail = vi.fn()
const deleteApplicationRecord = vi.fn()

vi.mock('@/api/workspace', () => ({
  getApplicationRecord: (...args: unknown[]) => getApplicationRecord(...args),
  updateApplicationRecord: (...args: unknown[]) => updateApplicationRecord(...args),
  saveStageDetail: (...args: unknown[]) => saveStageDetail(...args),
  deleteStageDetail: (...args: unknown[]) => deleteStageDetail(...args),
  deleteApplicationRecord: (...args: unknown[]) => deleteApplicationRecord(...args),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'app-1' }, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  RouterLink: { template: '<a><slot /></a>' },
}))

const record = {
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
  notes: '内推码 ABC123',
  closed_reason: null,
  rejected_stage: null,
  announcement_id: 'ann-1',
  position_id: 'pos-1',
  job_id: null,
  row_version: 2,
  created_at: '2026-03-02T09:00:00+00:00',
  updated_at: '2026-03-05T09:00:00+00:00',
  events: [
    {
      id: 'e1',
      event_type: 'created',
      from_status: null,
      to_status: 'applied',
      note: null,
      created_at: '2026-03-02T09:00:00+00:00',
    },
    {
      id: 'e2',
      event_type: 'status_changed',
      from_status: 'not_applied',
      to_status: 'applied',
      note: '官网投递完成',
      created_at: '2026-03-03T09:00:00+00:00',
    },
  ],
  stage_details: [],
  allowed_transitions: ['written_test', 'interview_done', 'offer', 'rejected', 'withdrawn'],
  recommended_missing: [],
}

function mountView() {
  return mount(ApplicationDetailView, {
    global: {
      plugins: [ElementPlus],
      stubs: {
        StageDetailForm: true,
        RouterLink: { template: '<a><slot /></a>' },
      },
    },
  })
}

describe('ApplicationDetailView', () => {
  beforeEach(() => {
    getApplicationRecord.mockReset().mockResolvedValue({ ...record })
    updateApplicationRecord.mockReset()
    saveStageDetail.mockReset()
    deleteStageDetail.mockReset()
    deleteApplicationRecord.mockReset()
  })

  it('渲染公司、岗位、状态与三阶段详情区', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('星河智能')
    expect(wrapper.text()).toContain('后端开发工程师')
    expect(wrapper.text()).toContain('已投递')
    expect(wrapper.text()).toContain('已笔试详情')
    expect(wrapper.text()).toContain('已面试详情')
    expect(wrapper.text()).toContain('面试通过详情')
    expect(wrapper.text()).toContain('可留空，随时补录')
  })

  it('时间线展示事件与状态迁移', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('创建记录')
    expect(wrapper.text()).toContain('状态变更')
    expect(wrapper.text()).toContain('未投递 → 已投递')
    expect(wrapper.text()).toContain('官网投递完成')
  })

  it('缺少推荐字段时给出黄色提示但不阻塞', async () => {
    getApplicationRecord.mockResolvedValueOnce({
      ...record,
      status: 'offer',
      status_label: '面试通过',
      is_terminal: true,
      recommended_missing: ['base_city', 'start_date'],
    })
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('建议补充：base 地、入职时间')
    expect(wrapper.find('.detail-hint').exists()).toBe(true)
  })

  it('点击状态按钮时带上 row_version', async () => {
    updateApplicationRecord.mockResolvedValueOnce({ ...record, status: 'written_test', row_version: 3 })
    const wrapper = mountView()
    await flushPromises()

    const button = wrapper
      .findAll('.status-actions button')
      .find((item) => item.text().includes('已笔试'))
    expect(button).toBeTruthy()
    await button!.trigger('click')
    await flushPromises()

    expect(updateApplicationRecord).toHaveBeenCalledWith('app-1', {
      status: 'written_test',
      row_version: 2,
    })
  })

  it('接口失败时展示错误态', async () => {
    getApplicationRecord.mockRejectedValueOnce(new Error('not found'))
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('not found')
    expect(wrapper.text()).toContain('重新加载')
  })
})
