import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ResumeTemplatePicker from '@/components/ResumeTemplatePicker.vue'

describe('ResumeTemplatePicker', () => {
  it('渲染四种模板并高亮当前模板', () => {
    const wrapper = mount(ResumeTemplatePicker, { props: { modelValue: 'elegant' } })

    expect(wrapper.findAll('.template-card')).toHaveLength(4)
    const active = wrapper.find('.template-card--active')
    expect(active.attributes('data-template')).toBe('elegant')
    expect(active.attributes('aria-pressed')).toBe('true')
  })

  it('点击模板卡片会发出 update:modelValue', async () => {
    const wrapper = mount(ResumeTemplatePicker, { props: { modelValue: 'classic' } })

    await wrapper.find('[data-template="compact"]').trigger('click')

    expect(wrapper.emitted('update:modelValue')).toEqual([['compact']])
  })
})
