import { apiClient } from './client'
import type {
  ApplicationDetail,
  ApplicationStatus,
  ApplicationSummary,
  PersonalizationResult,
} from '@/types/applications'

export async function listApplications(status?: ApplicationStatus): Promise<{
  items: ApplicationSummary[]
  total: number
}> {
  const response = await apiClient.get('/applications', { params: { status } })
  return response.data
}

export async function createApplication(payload: {
  job_id: string
  status?: ApplicationStatus
  notes?: string
}): Promise<ApplicationSummary> {
  const response = await apiClient.post('/applications', payload)
  return response.data
}

export async function getApplication(applicationId: string): Promise<ApplicationDetail> {
  const response = await apiClient.get(`/applications/${applicationId}`)
  return response.data
}

export async function updateApplication(
  applicationId: string,
  payload: { status?: ApplicationStatus; notes?: string; event_note?: string },
): Promise<ApplicationDetail> {
  const response = await apiClient.patch(`/applications/${applicationId}`, payload)
  return response.data
}

export async function saveMatchFeedback(
  jobId: string,
  payload: { relevant: boolean; reason?: string },
): Promise<void> {
  await apiClient.put(`/jobs/${jobId}/feedback`, payload)
}

export async function generatePersonalization(
  jobId: string,
  resumeDocumentId: string,
): Promise<PersonalizationResult> {
  const response = await apiClient.post(`/jobs/${jobId}/personalization`, {
    resume_document_id: resumeDocumentId,
  })
  return response.data
}
