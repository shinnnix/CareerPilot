<script setup lang="ts">
import { Calendar, Location, OfficeBuilding } from '@element-plus/icons-vue'

import type { Job } from '@/types/jobs'

defineProps<{
  job: Job
}>()

const remoteLabels = {
  onsite: '现场',
  hybrid: '混合',
  remote: '远程',
} as const
</script>

<template>
  <article class="job-card">
    <div class="job-card__top">
      <span :class="['status-dot', `status-dot--${job.status}`]">
        {{ job.status === 'active' ? '招聘中' : '已归档' }}
      </span>
      <span class="remote-badge">{{ remoteLabels[job.remote_type] }}</span>
    </div>
    <div>
      <p class="eyebrow">
        <el-icon><OfficeBuilding /></el-icon>
        {{ job.company_name }}
      </p>
      <h2>{{ job.title }}</h2>
    </div>
    <div class="job-meta">
      <span>
        <el-icon><Location /></el-icon>
        {{ job.city || '地点待确认' }}
      </span>
      <span>
        <el-icon><Calendar /></el-icon>
        {{ job.internship_days_per_week ? `${job.internship_days_per_week} 天/周` : '时间待确认' }}
      </span>
    </div>
    <div class="skill-list">
      <el-tag
        v-for="skill in job.required_skills.slice(0, 4)"
        :key="skill"
        effect="plain"
        round
      >
        {{ skill }}
      </el-tag>
    </div>
    <RouterLink class="card-link" :to="`/jobs/${job.id}`">
      查看职位详情
      <span aria-hidden="true">→</span>
    </RouterLink>
  </article>
</template>

