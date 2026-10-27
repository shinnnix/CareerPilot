import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it, vi } from 'vitest'

import JobAnnouncementView from '@/views/JobAnnouncementView.vue'

const getJobAnnouncement = vi.fn()
const markJob = vi.fn()
const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }))

vi.mock('@/api/workspace', () => ({
  getJobAnnouncement: (...args: unknown[]) => getJobAnnouncement(...args),
  markJob: (...args: unknown[]) => markJob(...args),
}))

const listResumes = vi.fn()

vi.mock('@/api/resumes', () => ({
  listResumes: (...args: unknown[]) => listResumes(...args),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'ann-1' }, query: {} }),
  useRouter: () => ({ push: pushMock, replace: vi.fn() }),
  RouterLink: { template: '<a><slot /></a>' },
}))

const announcement = {
  id: 'ann-1',
  title: '星河智能2027届校园招聘公告',
  company: { name: '星河智能', type: '民企', scale: '1000-5000人', industry: '人工智能' },
  recruitment_type: '秋招',
  target_cohort: '2027届',
  locations: ['上海', '深圳'],
  positions_text: '后端开发工程师、算法工程师',
  announcement_url: null,
  source_url: 'https://mp.weixin.qq.com/s/abc',
  source_channel: 'wechat_article',
  published_at: '2026-09-01T00:00:00+00:00',
  deadline: { text: '2026-11-30', at: '2026-11-30' },
  raw_text: '星河智能2027届秋季校园招聘正式启动。',
  apply_method: {
    emails: ['campus@xinghe.example.com'],
    links: [],
    note: '投递方式：邮件',
  },
  snapshot_at: '2026-09-02T08:00:00+00:00',
  status: 'active',
  visibility: 'private',
  mark_status: 'deferred',
  mark_status_label: '暂不投递',
  mark_note: '等春招',
  positions: [
    {
      id: 'pos-1',
      title: '后端开发工程师',
      category: '研发',
      city: '上海',
      education: '本科',
      headcount: '5',
      jd_text: null,
      sort_order: 0,
      application_id: null,
      application_status: null,
      application_status_label: null,
    },
    {
      id: 'pos-2',
      title: '算法工程师',
      category: '算法',
      city: '深圳',
      education: '硕士',
      headcount: '3',
      jd_text: null,
      sort_order: 1,
      application_id: 'app-1',
      application_status: 'applied',
      application_status_label: '已投递',
    },
  ],
  source: { kind: 'wechat_article', name: '星河智能招聘', url: 'https://mp.weixin.qq.com/s/abc' },
  created_at: '2026-09-02T08:00:00+00:00',
  updated_at: '2026-09-02T08:00:00+00:00',
}

function mountView() {
  return mount(JobAnnouncementView, {
    global: {
      plugins: [ElementPlus],
      stubs: {
        ApplicationFormDialog: true,
        // Render dialogs inline so assertions do not depend on teleport timing.
        ElDialog: {
          props: ['modelValue'],
          template:
            '<div v-if="modelValue" class="stub-dialog"><slot /><slot name="footer" /></div>',
        },
        RouterLink: { template: '<a><slot /></a>' },
      },
    },
  })
}

describe('JobAnnouncementView', () => {
  it('渲染公告头部、岗位清单与出处', async () => {
    getJobAnnouncement.mockResolvedValueOnce(announcement)
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('星河智能2027届校园招聘公告')
    expect(wrapper.text()).toContain('岗位清单')
    expect(wrapper.text()).toContain('后端开发工程师')
    expect(wrapper.text()).toContain('算法工程师')
    expect(wrapper.text()).toContain('campus@xinghe.example.com')
    expect(wrapper.text()).toContain('公告全文')
    expect(wrapper.text()).toContain('星河智能2027届秋季校园招聘正式启动。')
    expect(wrapper.text()).toContain('等春招')
    expect(wrapper.text()).toContain('暂不投递')
    expect(wrapper.text()).toContain('已投递')
  })

  it('已投递的岗位禁用创建按钮', async () => {
    getJobAnnouncement.mockResolvedValueOnce(announcement)
    const wrapper = mountView()
    await flushPromises()

    const buttons = wrapper.findAll('.position-table button')
    const labels = buttons.map((button) => button.text())
    expect(labels).toContain('创建投递')
    expect(labels).toContain('已投递')
    const applied = buttons.find((button) => button.text() === '已投递')
    expect(applied!.attributes('disabled')).toBeDefined()
  })

  it('接口失败时展示错误提示', async () => {
    getJobAnnouncement.mockRejectedValueOnce(new Error('公告不存在'))
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('公告不存在')
  })

  it('岗位全部投递后主按钮禁用', async () => {
    const fullyApplied = {
      ...announcement,
      positions: announcement.positions.map((position) => ({
        ...position,
        application_id: 'app-1',
        application_status: 'applied',
        application_status_label: '已投递',
      })),
    }
    getJobAnnouncement.mockResolvedValueOnce(fullyApplied)
    const wrapper = mountView()
    await flushPromises()

    const create = wrapper
      .findAll('.detail-actions button')
      .find((button) => button.text() === '创建投递记录')
    expect(create).toBeDefined()
    expect(create!.attributes('disabled')).toBeDefined()
  })

  it('可以把公告交给简历工作台做 AI 优化（模块一 → 模块三）', async () => {
    getJobAnnouncement.mockResolvedValueOnce(announcement)
    listResumes.mockResolvedValueOnce({
      items: [
        {
          id: 'resume-1',
          title: '我的简历',
          candidate_name: '张三',
          content_version: 3,
        },
      ],
      page: 1,
      page_size: 100,
      total: 1,
    })
    const wrapper = mountView()
    await flushPromises()

    const action = wrapper
      .findAll('button')
      .find((button) => button.text() === '用简历优化这个 JD')
    expect(action).toBeDefined()
    await action!.trigger('click')
    await flushPromises()

    expect(listResumes).toHaveBeenCalled()
    const confirm = wrapper
      .findAll('.stub-dialog button')
      .find((button) => button.text() === '打开简历工作台')
    expect(confirm).toBeDefined()
    await confirm!.trigger('click')
    await flushPromises()

    expect(pushMock).toHaveBeenCalledWith({
      path: '/workspace/resumes/resume-1',
      query: { announcement: 'ann-1', optimize: '1' },
    })
  })
})
