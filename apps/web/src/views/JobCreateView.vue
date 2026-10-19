<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { createJob } from '@/api/jobs'
import { getApiErrorMessage } from '@/api/errors'
import JobForm from '@/components/JobForm.vue'
import type { JobInput } from '@/types/jobs'

const router = useRouter()
const submitting = ref(false)

async function handleSubmit(payload: JobInput) {
  submitting.value = true
  try {
    const job = await createJob(payload)
    ElMessage.success('职位已创建')
    await router.push(`/jobs/${job.id}`)
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="page page--narrow">
    <div class="page-heading">
      <div>
        <p class="eyebrow">CREATE JOB</p>
        <h1>添加职位</h1>
        <p>先保留完整 JD 和关键字段，为后续 RAG 数据处理打好基础。</p>
      </div>
    </div>
    <section class="surface">
      <JobForm
        :submitting="submitting"
        submit-label="创建职位"
        @submit="handleSubmit"
        @cancel="router.push('/')"
      />
    </section>
  </main>
</template>

