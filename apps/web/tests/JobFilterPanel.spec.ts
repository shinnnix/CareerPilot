import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it } from 'vitest'

import JobFilterPanel from '@/components/JobFilterPanel.vue'
import type { JobFacets, JobFilters } from '@/types/workspace'

const filters: JobFilters = {
  keyword: '',
  company: '',
  status: '',
  company_type: '',
  recruitment_type: '',
  target_cohort: '',
  location: '',
  job_category: '',
  sort: 'updated_desc',
  page: 1,
  page_size: 20,
}

const facets: JobFacets = {
  company_types: [{ value: '民企', label: '民企', count: 2 }],
  recruitment_types: [{ value: '秋招', label: '秋招', count: 1 }],
  target_cohorts: [{ value: '2027届', label: '2027届', count: 1 }],
  locations: [{ value: '上海', label: '上海', count: 2 }],
  job_categories: [{ value: '研发', label: '研发', count: 1 }],
  statuses: [{ value: 'not_applied', label: '未投递', count: 2 }],
}

function mountPanel(overrides: Partial<JobFilters> = {}) {
  return mount(JobFilterPanel, {
    props: {
      modelValue: { ...filters, ...overrides },
      facets,
      advancedOpen: false,
    },
    global: { plugins: [ElementPlus] },
  })
}

describe('JobFilterPanel', () => {
  it('输入关键词后点击搜索会发出 search', async () => {
    const wrapper = mountPanel()
    await wrapper.find('input').setValue('RAG')
    const buttons = wrapper.findAll('button')
    const searchButton = buttons.find((button) => button.text() === '搜索')
    await searchButton!.trigger('click')

    expect(wrapper.emitted('update:modelValue')?.[0]?.[0]).toMatchObject({ keyword: 'RAG' })
    expect(wrapper.emitted('search')).toHaveLength(1)
  })

  it('高级筛选默认折叠，点击后发出展开事件', async () => {
    const wrapper = mountPanel()
    const advancedRow = wrapper.find('.filter-row--advanced')
    expect(advancedRow.isVisible()).toBe(false)

    const buttons = wrapper.findAll('button')
    const toggle = buttons.find((button) => button.text().includes('高级筛选'))
    await toggle!.trigger('click')

    expect(wrapper.emitted('update:advancedOpen')).toEqual([[true]])
  })

  it('重置按钮只发出 reset，由父级决定清空哪些字段', async () => {
    const wrapper = mountPanel({ keyword: '后端' })
    const buttons = wrapper.findAll('button')
    const resetButton = buttons.find((button) => button.text() === '重置')
    await resetButton!.trigger('click')

    expect(wrapper.emitted('reset')).toHaveLength(1)
  })
})
