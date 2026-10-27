import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ResumePreview from '@/components/ResumePreview.vue'
import type { ResumeHead, ResumeSection } from '@/types/resumes'

const head: ResumeHead = {
  name: '沈鑫',
  target_title: 'AI 应用开发实习生',
  phone: '19923458371',
  email: 'shenxin@example.com',
  city: null,
  links: [],
}

const sections: ResumeSection[] = [
  {
    id: 'section-0',
    key: 'education',
    title: '教育经历',
    entries: [
      {
        id: 'section-0-entry-0',
        title: '西安石油大学',
        subtitle: '新能源科学与工程 · 本科',
        period: '2019.09-2023.06',
        bullets: ['专业成绩：综测排名前 50%'],
      },
    ],
  },
  {
    id: 'section-1',
    key: 'summary',
    title: '自我评价',
    entries: [
      {
        id: 'section-1-entry-0',
        title: '有较强的工程落地能力，喜欢把复杂问题拆成可验证的小步骤。',
        subtitle: null,
        period: null,
        bullets: [],
      },
    ],
  },
]

describe('ResumePreview', () => {
  it('按模板与字号渲染抬头、时间线和条目', () => {
    const wrapper = mount(ResumePreview, {
      props: { head, sections, template: 'modern', fontSize: 16 },
    })

    const paper = wrapper.find('.resume-paper')
    expect(paper.attributes('data-template')).toBe('modern')
    expect(paper.attributes('style')).toContain('font-size: 16px')
    expect(wrapper.text()).toContain('沈鑫')
    expect(wrapper.text()).toContain('AI 应用开发实习生')
    expect(wrapper.text()).toContain('西安石油大学')
    expect(wrapper.text()).toContain('2019.09-2023.06')
    expect(wrapper.text()).toContain('专业成绩：综测排名前 50%')
    expect(wrapper.findAll('.resume-section')).toHaveLength(2)
    expect(wrapper.find('.resume-paragraph').text()).toContain('有较强的工程落地能力')
  })

  it('空章节给出提示，交互模式下点击章节会发出 select', async () => {
    const emptySections: ResumeSection[] = [
      { id: 'section-2', key: 'project', title: '项目经历', entries: [] },
    ]
    const wrapper = mount(ResumePreview, {
      props: { head, sections: emptySections, interactive: true },
    })

    expect(wrapper.find('.resume-section-empty').exists()).toBe(true)
    await wrapper.find('.resume-section').trigger('click')
    expect(wrapper.emitted('select')).toEqual([['section-2']])
  })

  it('showEmpty=false 时隐藏空章节，用于建议稿预览', () => {
    const wrapper = mount(ResumePreview, {
      props: {
        head,
        sections: [
          ...sections,
          { id: 'section-2', key: 'project', title: '项目经历', entries: [] },
        ],
        showEmpty: false,
      },
    })

    expect(wrapper.findAll('.resume-section')).toHaveLength(2)
  })
})
