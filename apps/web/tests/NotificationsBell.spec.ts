import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it, vi } from 'vitest'

import NotificationsBell from '@/components/NotificationsBell.vue'

const listReminders = vi.fn()
const getReminderSummary = vi.fn()
const completeReminder = vi.fn()
const dismissReminder = vi.fn()
const snoozeReminder = vi.fn()
const pushMock = vi.fn()

vi.mock('@/api/workspace', () => ({
  listReminders: (...args: unknown[]) => listReminders(...args),
  getReminderSummary: (...args: unknown[]) => getReminderSummary(...args),
  completeReminder: (...args: unknown[]) => completeReminder(...args),
  dismissReminder: (...args: unknown[]) => dismissReminder(...args),
  snoozeReminder: (...args: unknown[]) => snoozeReminder(...args),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
}))

const reminder = {
  id: 'rem-1',
  application_id: 'app-1',
  rule_type: 'follow_up_due',
  title: '该跟进「星河智能 · 后端开发」了',
  body: '到达你设置的跟进日期。',
  due_at: '2026-10-20T09:00:00+00:00',
  status: 'pending',
  snoozed_until: null,
  done_at: null,
  created_at: '2026-10-20T09:00:00+00:00',
}

function mountBell() {
  return mount(NotificationsBell, {
    global: {
      plugins: [ElementPlus],
      stubs: {
        ElPopover: {
          template: '<div><slot name="reference" /><slot /></div>',
        },
        ElBadge: {
          props: ['value', 'hidden'],
          template: '<span class="stub-badge"><slot /><b>{{ hidden ? "" : value }}</b></span>',
        },
      },
    },
  })
}

describe('NotificationsBell', () => {
  it('加载提醒并在徽标显示待处理数量', async () => {
    getReminderSummary.mockResolvedValueOnce({ pending: 1, due_now: 1 })
    listReminders.mockResolvedValueOnce({
      items: [reminder],
      total: 1,
      pending: 1,
      due_now: 1,
    })

    const wrapper = mountBell()
    await flushPromises()

    expect(listReminders).toHaveBeenCalled()
    expect(wrapper.find('.stub-badge b').text()).toBe('1')
    expect(wrapper.text()).toContain('该跟进「星河智能 · 后端开发」了')
    expect(wrapper.text()).toContain('到期')
  })

  it('完成提醒会调用接口并刷新列表', async () => {
    getReminderSummary.mockResolvedValue({ pending: 1, due_now: 1 })
    listReminders.mockResolvedValue({
      items: [reminder],
      total: 1,
      pending: 1,
      due_now: 1,
    })
    completeReminder.mockResolvedValueOnce({ ...reminder, status: 'done' })

    const wrapper = mountBell()
    await flushPromises()

    const done = wrapper.findAll('button').find((button) => button.text() === '完成')
    expect(done).toBeDefined()
    await done!.trigger('click')
    await flushPromises()

    expect(completeReminder).toHaveBeenCalledWith('rem-1')
    expect(listReminders.mock.calls.length).toBeGreaterThanOrEqual(2)
  })

  it('点击标题跳转到对应投递记录', async () => {
    getReminderSummary.mockResolvedValueOnce({ pending: 1, due_now: 0 })
    listReminders.mockResolvedValueOnce({
      items: [reminder],
      total: 1,
      pending: 1,
      due_now: 0,
    })

    const wrapper = mountBell()
    await flushPromises()

    await wrapper.find('.reminder-title-btn').trigger('click')

    expect(pushMock).toHaveBeenCalledWith('/workspace/applications/app-1')
  })
})
