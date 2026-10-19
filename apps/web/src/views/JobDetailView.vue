<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Delete, Edit, Link } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'

import { deleteJob, getJob, updateJob } from '@/api/jobs'
import { getApiErrorMessage } from '@/api/errors'
import JobForm from '@/components/JobForm.vue'
import type { Job, JobInput } from '@/types/jobs'

const route = useRoute()
const router = useRouter()
const job = ref<Job | null>(null)
const loading = ref(true)
const errorMessage = ref('')
const editing = ref(false)
const submitting = ref(false)

const jobId = computed(() => String(route.params.id))

async function loadJob() {
  loading.value = true
  errorMessage.value = ''
  try {
    job.value = await getJob(jobId.value)
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  } finally {
    loading.value = false
  }
}

async function handleUpdate(payload: JobInput) {
  submitting.value = true
  try {
    job.value = await updateJob(jobId.value, payload)
    editing.value = false
    ElMessage.success('职位已更新')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

async function handleDelete() {
  const confirmed = await ElMessageBox.confirm(
    '删除后无法在职位列表中恢复，确认删除吗？',
    '删除职位',
    {
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
      type: 'warning',
    },
  )
    .then(() => true)
    .catch(() => false)
  if (!confirmed) return
  try {
    await deleteJob(jobId.value)
    ElMessage.success('职位已删除')
    await router.push('/')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

onMounted(loadJob)
</script>

<template>
  <main class="page page--narrow">
    <RouterLink class="back-link" to="/">
      <el-icon><ArrowLeft /></el-icon>
      返回职位列表
    </RouterLink>

    <el-skeleton v-if="loading" :rows="10" animated class="surface" />

    <el-result
      v-else-if="errorMessage"
      icon="error"
      title="无法加载职位"
      :sub-title="errorMessage"
    >
      <template #extra>
        <el-button @click="loadJob">重新加载</el-button>
      </template>
    </el-result>

    <template v-else-if="job">
      <section v-if="editing" class="surface">
        <div class="section-heading">
          <div>
            <p class="eyebrow">EDIT JOB</p>
            <h1>编辑职位</h1>
          </div>
        </div>
        <JobForm
          :job="job"
          :submitting="submitting"
          submit-label="保存修改"
          @submit="handleUpdate"
          @cancel="editing = false"
        />
      </section>

      <template v-else>
        <section class="detail-hero">
          <div>
            <span :class="['status-dot', `status-dot--${job.status}`]">
              {{ job.status === 'active' ? '招聘中' : '已归档' }}
            </span>
            <p class="eyebrow">{{ job.company_name }}</p>
            <h1>{{ job.title }}</h1>
            <p class="detail-subtitle">
              {{ job.city || '地点待确认' }} ·
              {{ job.remote_type === 'remote' ? '远程' : job.remote_type === 'hybrid' ? '混合办公' : '现场办公' }}
            </p>
          </div>
          <div class="detail-actions">
            <RouterLink :to="`/jobs/${job.id}/match`">
              <el-button type="primary">查看匹配报告</el-button>
            </RouterLink>
            <el-button :icon="Edit" @click="editing = true">编辑</el-button>
            <el-button type="danger" plain :icon="Delete" @click="handleDelete">删除</el-button>
          </div>
        </section>

        <div class="detail-grid">
          <section class="surface detail-content">
            <div>
              <p class="eyebrow">JOB DESCRIPTION</p>
              <h2>职位描述</h2>
            </div>
            <p class="raw-text">{{ job.raw_text }}</p>
          </section>

          <aside class="detail-sidebar">
            <section class="surface">
              <p class="eyebrow">REQUIREMENTS</p>
              <h2>关键信息</h2>
              <dl class="fact-list">
                <div>
                  <dt>每周时间</dt>
                  <dd>{{ job.internship_days_per_week ? `${job.internship_days_per_week} 天` : '待确认' }}</dd>
                </div>
                <div>
                  <dt>实习周期</dt>
                  <dd>{{ job.internship_months ? `${job.internship_months} 个月` : '待确认' }}</dd>
                </div>
                <div>
                  <dt>薪资范围</dt>
                  <dd>
                    {{ job.salary_min || job.salary_max
                      ? `${job.salary_min || '?'} – ${job.salary_max || '?'}`
                      : '待确认' }}
                  </dd>
                </div>
              </dl>
            </section>
            <section class="surface">
              <p class="eyebrow">SKILLS</p>
              <h2>技能标签</h2>
              <div class="skill-list">
                <el-tag v-for="skill in job.required_skills" :key="skill" round>
                  {{ skill }}
                </el-tag>
                <el-tag
                  v-for="skill in job.preferred_skills"
                  :key="`preferred-${skill}`"
                  type="info"
                  effect="plain"
                  round
                >
                  + {{ skill }}
                </el-tag>
              </div>
            </section>
            <a
              v-if="job.source_url"
              class="source-link"
              :href="job.source_url"
              target="_blank"
              rel="noreferrer"
            >
              <el-icon><Link /></el-icon>
              查看职位来源
            </a>
          </aside>
        </div>
      </template>
    </template>
  </main>
</template>
