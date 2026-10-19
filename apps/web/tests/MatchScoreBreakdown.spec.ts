import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import MatchScoreBreakdown from '@/components/MatchScoreBreakdown.vue'

describe('MatchScoreBreakdown', () => {
  it('把 0-1 的后端分项转换成百分比并保留可解释标签', () => {
    const wrapper = mount(MatchScoreBreakdown, {
      props: {
        breakdown: {
          required_skill_coverage: 0.75,
          experience_semantic_score: 0.5,
        },
      },
      global: {
        stubs: {
          ElProgress: {
            props: ['percentage'],
            template: '<span class="progress">{{ percentage }}</span>',
          },
        },
      },
    })
    expect(wrapper.text()).toContain('必备技能')
    expect(wrapper.text()).toContain('经历语义')
    expect(wrapper.findAll('.progress').map((node) => node.text())).toEqual(['75', '50'])
  })
})
