import { apiClient } from './client'
import type {
  Job,
  JobInput,
  JobListResponse,
  JobPatch,
  JobSearchParams,
} from '@/types/jobs'

export async function listJobs(params: JobSearchParams): Promise<JobListResponse> {
  const response = await apiClient.get<JobListResponse>('/jobs', { params })
  return response.data
}

export async function getJob(jobId: string): Promise<Job> {
  const response = await apiClient.get<Job>(`/jobs/${jobId}`)
  return response.data
}

export async function createJob(payload: JobInput): Promise<Job> {
  const response = await apiClient.post<Job>('/jobs', payload)
  return response.data
}

export async function updateJob(jobId: string, payload: JobPatch): Promise<Job> {
  const response = await apiClient.patch<Job>(`/jobs/${jobId}`, payload)
  return response.data
}

export async function deleteJob(jobId: string): Promise<void> {
  await apiClient.delete(`/jobs/${jobId}`)
}

