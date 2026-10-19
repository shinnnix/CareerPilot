import { reactive, ref } from 'vue'

import { listJobs } from '@/api/jobs'
import { getApiErrorMessage } from '@/api/errors'
import type { Job, JobSearchParams } from '@/types/jobs'

export function useJobs() {
  const jobs = ref<Job[]>([])
  const loading = ref(false)
  const errorMessage = ref('')
  const total = ref(0)
  const query = reactive<JobSearchParams>({
    keyword: '',
    city: '',
    status: 'active',
    page: 1,
    page_size: 9,
  })

  async function search() {
    loading.value = true
    errorMessage.value = ''
    try {
      const result = await listJobs(query)
      jobs.value = result.items
      total.value = result.total
    } catch (error) {
      errorMessage.value = getApiErrorMessage(error)
      jobs.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  return { jobs, loading, errorMessage, total, query, search }
}

