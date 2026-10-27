import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ApplicationManualDialog from '@/components/ApplicationManualDialog.vue'

const createApplications = vi.fn()

vi.mock('@/api/workspace', () => ({
  createApplications: (...args: unknown[]) => createApplications(...args),
}))

function mountDialog() {
  return mount(ApplicationManualDialog, {
    props: { modelValue: false },
    attachTo: document.body,
    global: { plugins: [ElementPlus] },
  })
}

async function fillCompanyAndPosition(wrapper: ReturnType<typeof mountDialog>) {
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  const company = document.querySelector<HTMLInputElement>('input[placeholder="例如：星河智能"]')
  const position = document.querySelector<HTMLInputElement>(
    'input[placeholder="例如：后端开发工程师"]',
  )
  expect(company).toBeTruthy()
  expect(position).toBeTruthy()
  company!.value = '星河智能'
  company!.dispatchEvent(new Event('input'))
  position!.value = '后端开发工程师'
  position!.dispatchEvent(new Event('input'))
  await flushPromises()
}

function submitButton(): HTMLButtonElement | undefined {
  const buttons = Array.from(document.querySelectorAll<HTMLButtonElement>('.el-dialog button'))
  return buttons.find((button) => button.textContent?.trim() === '保存')
}

describe('ApplicationManualDialog', () => {
  beforeEach(() => {
    createApplications.mockReset().mockResolvedValue({ items: [{ id: 'app-1' }], total: 1 })
  })

  it('公司或岗位为空时不发请求', async () => {
    const wrapper = mountDialog()
    await wrapper.setProps({ modelValue: true })
    await flushPromises()

    submitButton()!.click()
    await flushPromises()

    expect(createApplications).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('填写后按计划字段提交', async () => {
    const wrapper = mountDialog()
    await fillCompanyAndPosition(wrapper)

    submitButton()!.click()
    await flushPromises()

    expect(createApplications).toHaveBeenCalledTimes(1)
    const payload = createApplications.mock.calls[0][0] as Record<string, unknown>
    expect(payload.company_name).toBe('星河智能')
    expect(payload.position_title).toBe('后端开发工程师')
    expect(payload.status).toBe('applied')
    expect(payload.channel).toBe('官网')
    expect(payload.allow_duplicate).toBe(false)
    expect(typeof payload.applied_at).toBe('string')
    wrapper.unmount()
  })
})
