import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it } from 'vitest'
import { nextTick } from 'vue'

import ColumnSettings from '@/components/ColumnSettings.vue'

const columns = [
  { key: 'company_name', label: '公司名称', default: true },
  { key: 'positions', label: '岗位', default: true },
  { key: 'deadline', label: '投递截止', default: true },
]

function mountSettings(visible: string[]) {
  return mount(ColumnSettings, {
    props: { columns, visible },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

describe('ColumnSettings', () => {
  it('显示已选列数 / 总列数', () => {
    const wrapper = mountSettings(['company_name', 'positions'])

    expect(wrapper.text()).toContain('列设置')
    expect(wrapper.text()).toContain('2/3')
  })

  it('展开后渲染全部列，剩余一列时禁用该列', async () => {
    const wrapper = mountSettings(['positions'])
    await wrapper.find('.column-settings-trigger').trigger('click')
    await nextTick()

    const checkboxes = Array.from(document.querySelectorAll('.column-settings-list .el-checkbox'))
    const byLabel = new Map<string, Element[]>()
    checkboxes.forEach((item) => {
      const label = (item.textContent || '').trim()
      byLabel.set(label, [...(byLabel.get(label) || []), item])
    })
    expect([...byLabel.keys()].sort()).toEqual(['公司名称', '投递截止', '岗位'].sort())

    const disabledLabels = [...byLabel.entries()]
      .filter(([, nodes]) => nodes.some((node) => node.classList.contains('is-disabled')))
      .map(([label]) => label)
    expect(disabledLabels).toEqual(['岗位'])

    wrapper.unmount()
  })
})
