import { beforeAll, describe, expect, it } from 'vitest'

import router from '@/router'

beforeAll(() => {
  // jsdom does not implement scrollTo; router scrollBehavior calls it on navigation.
  Object.defineProperty(window, 'scrollTo', { value: () => {}, writable: true })
})

async function resolvePath(target: string): Promise<string> {
  await router.push(target)
  return router.currentRoute.value.path
}

describe('legacy route redirects', () => {
  it('把根路径带到职位信息', async () => {
    expect(await resolvePath('/')).toBe('/workspace/jobs')
  })

  it('迁移 /jobs 家族，包括新建、详情与匹配报告', async () => {
    // 手工新建职位已被「导入职位」取代，旧链接收敛到列表并打开导入弹窗
    await router.push('/jobs/new')
    expect(router.currentRoute.value.path).toBe('/workspace/jobs')
    expect(router.currentRoute.value.query.import).toBe('1')

    expect(await resolvePath('/jobs/job-1')).toBe('/workspace/jobs/job-1')
    expect(await resolvePath('/jobs/job-1/match')).toBe('/workspace/jobs/job-1/match')
  })

  it('迁移 /resumes 家族并保留 query', async () => {
    expect(await resolvePath('/resumes')).toBe('/workspace/resumes')
    expect(await resolvePath('/resumes/resume-1')).toBe('/workspace/resumes/resume-1')

    await router.push('/resumes/resume-1?job=job-1&optimize=1')
    expect(router.currentRoute.value.path).toBe('/workspace/resumes/resume-1')
    expect(router.currentRoute.value.query).toEqual({ job: 'job-1', optimize: '1' })
  })

  it('把 /knowledge 映射到资料库，保留文档 id', async () => {
    expect(await resolvePath('/knowledge')).toBe('/workspace/library')
    expect(await resolvePath('/knowledge/doc-1')).toBe('/workspace/library/doc-1')
  })

  it('收敛检索、Agent 与投递记录', async () => {
    expect(await resolvePath('/retrieval')).toBe('/workspace/evidence')
    expect(await resolvePath('/agent')).toBe('/workspace/assistant')
    expect(await resolvePath('/applications')).toBe('/workspace/applications')
    // 详情页已建（P0-4），旧链接带 id 时落到详情而不是列表
    expect(await resolvePath('/applications/app-1')).toBe('/workspace/applications/app-1')
  })

  it('更多工具的三个新页面可直达且兼容旧根路径', async () => {
    expect(await resolvePath('/workspace/profile')).toBe('/workspace/profile')
    expect(await resolvePath('/workspace/extension')).toBe('/workspace/extension')
    expect(await resolvePath('/workspace/settings')).toBe('/workspace/settings')

    expect(await resolvePath('/profile')).toBe('/workspace/profile')
    expect(await resolvePath('/extension')).toBe('/workspace/extension')
    expect(await resolvePath('/settings')).toBe('/workspace/settings')
  })

  it('未知路径落到 404', async () => {
    expect(await resolvePath('/nope/nope')).toBe('/nope/nope')
    expect(router.currentRoute.value.name).toBe('not-found')
  })
})
