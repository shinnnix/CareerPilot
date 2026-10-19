import { createRouter, createWebHistory } from 'vue-router'

import JobCreateView from '@/views/JobCreateView.vue'
import JobDetailView from '@/views/JobDetailView.vue'
import JobListView from '@/views/JobListView.vue'
import DocumentDetailView from '@/views/DocumentDetailView.vue'
import KnowledgeBaseView from '@/views/KnowledgeBaseView.vue'
import NotFoundView from '@/views/NotFoundView.vue'
import RetrievalView from '@/views/RetrievalView.vue'
import MatchReportView from '@/views/MatchReportView.vue'
import AgentView from '@/views/AgentView.vue'
import ApplicationsView from '@/views/ApplicationsView.vue'
import LoginView from '@/views/LoginView.vue'
import { demoAuthEnabled, getAccessToken } from '@/auth-storage'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    { path: '/', name: 'jobs', component: JobListView },
    { path: '/jobs/new', name: 'job-create', component: JobCreateView },
    { path: '/jobs/:id', name: 'job-detail', component: JobDetailView },
    { path: '/jobs/:id/match', name: 'job-match', component: MatchReportView },
    { path: '/knowledge', name: 'knowledge', component: KnowledgeBaseView },
    { path: '/knowledge/:id', name: 'document-detail', component: DocumentDetailView },
    { path: '/retrieval', name: 'retrieval', component: RetrievalView },
    { path: '/agent', name: 'agent', component: AgentView },
    { path: '/applications', name: 'applications', component: ApplicationsView },
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
