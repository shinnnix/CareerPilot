import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createRouter, createWebHistory } from 'vue-router'

import JobCard from '@/components/JobCard.vue'
import type { Job } from '@/types/jobs'

const job: Job = {
  id: 'job-1',
  title: 'AI 应用开发实习生',
  company_name: '示例科技',
  city: '上海',
  employment_type: 'internship',
  remote_type: 'hybrid',
  salary_min: '200.00',
  salary_max: '300.00',
  internship_days_per_week: 4,
  internship_months: 4,
  required_skills: ['Python', 'FastAPI', 'RAG'],
  preferred_skills: ['Vue 3'],
  source_url: 'https://example.com/job',
  raw_text: '负责 AI 应用开发，使用 FastAPI、RAG 与 Vue 构建面向用户的智能产品。',
  status: 'active',
  created_at: '2026-07-29T00:00:00Z',
  updated_at: '2026-07-29T00:00:00Z',
}

describe('JobCard', () => {
  it('renders job identity, metadata and detail link', async () => {
    const router = createRouter({
      history: createWebHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/jobs/:id', component: { template: '<div />' } },
      ],
    })
    await router.push('/')
    await router.isReady()

    const wrapper = mount(JobCard, {
      props: { job },
      global: { plugins: [router, ElementPlus] },
    })

    expect(wrapper.text()).toContain('AI 应用开发实习生')
    expect(wrapper.text()).toContain('示例科技')
    expect(wrapper.text()).toContain('上海')
    expect(wrapper.text()).toContain('FastAPI')
    expect(wrapper.get('a').attributes('href')).toBe('/jobs/job-1')
  })
})
