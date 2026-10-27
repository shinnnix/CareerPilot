import { createRouter, createWebHistory } from 'vue-router'
import type { LocationQuery } from 'vue-router'

import WorkspaceLayout from '@/layouts/WorkspaceLayout.vue'
import JobAnnouncementView from '@/views/JobAnnouncementView.vue'
import JobListView from '@/views/JobListView.vue'
import DocumentDetailView from '@/views/DocumentDetailView.vue'
import KnowledgeBaseView from '@/views/KnowledgeBaseView.vue'
import NotFoundView from '@/views/NotFoundView.vue'
import RetrievalView from '@/views/RetrievalView.vue'
import MatchReportView from '@/views/MatchReportView.vue'
import AgentView from '@/views/AgentView.vue'
import ApplicationDetailView from '@/views/ApplicationDetailView.vue'
import ApplicationsView from '@/views/ApplicationsView.vue'
import ExtensionSetupView from '@/views/ExtensionSetupView.vue'
import LoginView from '@/views/LoginView.vue'
import ProfileView from '@/views/ProfileView.vue'
import ResumeListView from '@/views/ResumeListView.vue'
import ResumeWorkspaceView from '@/views/ResumeWorkspaceView.vue'
import SettingsView from '@/views/SettingsView.vue'
import { demoAuthEnabled, getAccessToken } from '@/auth-storage'

function keepQuery(to: { query: LocationQuery; hash: string }) {
  return { query: to.query, hash: to.hash }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    {
      path: '/workspace',
      component: WorkspaceLayout,
      children: [
        { path: '', redirect: { name: 'jobs' } },
        {
          path: 'jobs',
          name: 'jobs',
          component: JobListView,
          meta: { group: '工作空间', title: '职位信息' },
        },
        {
          // 手工新建职位已被「导入职位」取代（P0-3），保留旧链接可用
          path: 'jobs/new',
          redirect: { name: 'jobs', query: { import: '1' } },
        },
        {
          path: 'jobs/:id',
          name: 'job-announcement',
          component: JobAnnouncementView,
          meta: { group: '职位信息', title: '公告详情' },
        },
        {
          path: 'jobs/:id/match',
          name: 'job-match',
          component: MatchReportView,
          meta: { group: '职位信息', title: '匹配报告' },
        },
        {
          path: 'applications',
          name: 'applications',
          component: ApplicationsView,
          meta: { group: '工作空间', title: '投递记录' },
        },
        {
          path: 'applications/:id',
          name: 'application-detail',
          component: ApplicationDetailView,
          meta: { group: '投递记录', title: '投递详情' },
        },
        {
          path: 'resumes',
          name: 'resumes',
          component: ResumeListView,
          meta: { group: '工作空间', title: '我的简历' },
        },
        {
          path: 'resumes/:id',
          name: 'resume-workspace',
          component: ResumeWorkspaceView,
          meta: { group: '我的简历', title: '简历工作台' },
        },
        {
          path: 'library',
          name: 'library',
          component: KnowledgeBaseView,
          meta: { group: '更多工具', title: '资料库' },
        },
        {
          path: 'library/:id',
          name: 'document-detail',
          component: DocumentDetailView,
          meta: { group: '资料库', title: '资料详情' },
        },
        {
          path: 'evidence',
          name: 'evidence',
          component: RetrievalView,
          meta: { group: '更多工具', title: '证据检索' },
        },
        {
          path: 'assistant',
          name: 'assistant',
          component: AgentView,
          meta: { group: '更多工具', title: '求职 Agent' },
        },
        {
          path: 'profile',
          name: 'profile',
          component: ProfileView,
          meta: { group: '更多工具', title: '网申个人信息' },
        },
        {
          path: 'extension',
          name: 'extension',
          component: ExtensionSetupView,
          meta: { group: '更多工具', title: '网申填写插件' },
        },
        {
          path: 'settings',
          name: 'settings',
          component: SettingsView,
          meta: { group: '更多工具', title: 'AI 与设置' },
        },
      ],
    },

    // Legacy paths → /workspace/*
    { path: '/', redirect: { name: 'jobs' } },
    {
      path: '/jobs/:pathMatch(.*)*',
      redirect: (to) => ({ path: `/workspace${to.path}`, ...keepQuery(to) }),
    },
    {
      path: '/resumes/:pathMatch(.*)*',
      redirect: (to) => ({ path: `/workspace${to.path}`, ...keepQuery(to) }),
    },
    {
      // 投递详情页已建（P0-4），带 id 的旧链接直接落到详情
      path: '/applications/:pathMatch(.*)*',
      redirect: (to) => {
        const match = to.path.match(/^\/applications\/([^/]+)$/)
        if (match) return { path: `/workspace/applications/${match[1]}`, ...keepQuery(to) }
        return { path: '/workspace/applications', ...keepQuery(to) }
      },
    },
    {
      path: '/knowledge/:pathMatch(.*)*',
      redirect: (to) => ({
        path: to.path.replace(/^\/knowledge/, '/workspace/library'),
        ...keepQuery(to),
      }),
    },
    { path: '/retrieval', redirect: { name: 'evidence' } },
    { path: '/agent', redirect: { name: 'assistant' } },
    { path: '/settings', redirect: { name: 'settings' } },
    { path: '/profile', redirect: { name: 'profile' } },
    { path: '/extension', redirect: { name: 'extension' } },

    { path: '/:pathMatch(.*)*', name: 'not-found', component: NotFoundView },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach((to) => {
  if (to.meta.realAuth && !getAccessToken()) return { name: 'login', query: { redirect: to.fullPath } }
  if (to.meta.public || demoAuthEnabled() || getAccessToken()) return true
  return { name: 'login', query: { redirect: to.fullPath } }
})

export default router
