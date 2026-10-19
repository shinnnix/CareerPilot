import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AgentConfirmationCard from '@/components/AgentConfirmationCard.vue'

describe('AgentConfirmationCard', () => {
  it('明确展示写工具并分别发出确认和拒绝事件', async () => {
    const wrapper = mount(AgentConfirmationCard, {
      props: { toolName: 'create_application' },
      global: {
        stubs: {
          ElButton: { template: '<button><slot /></button>' },
        },
      },
    })
    expect(wrapper.text()).toContain('create_application')
    const buttons = wrapper.findAll('button')
    await buttons[0].trigger('click')
    await buttons[1].trigger('click')
    expect(wrapper.emitted('approve')).toHaveLength(1)
    expect(wrapper.emitted('reject')).toHaveLength(1)
  })
})
