import { apiClient } from './client'
import type {
  ResumeApplyResult,
  ResumeDetail,
  ResumeListResponse,
  ResumeManualCreateInput,
  ResumeOptimization,
  ResumeOptimizationListResponse,
  ResumeOptimizeInput,
  ResumeTemplate,
  ResumeTextImportInput,
  ResumeUpdateInput,
} from '@/types/resumes'

export async function listResumes(params: {
  page?: number
  page_size?: number
} = {}): Promise<ResumeListResponse> {
  const response = await apiClient.get<ResumeListResponse>('/resumes', { params })
  return response.data
}

export async function getResume(resumeId: string): Promise<ResumeDetail> {
  const response = await apiClient.get<ResumeDetail>(`/resumes/${resumeId}`)
  return response.data
}

export async function importResumeText(payload: ResumeTextImportInput): Promise<ResumeDetail> {
  const response = await apiClient.post<ResumeDetail>('/resumes/import/text', payload)
  return response.data
}

export async function uploadResumeFile(payload: {
  display_name: string
  file: File
  template?: ResumeTemplate
  target_job_id?: string | null
  target_announcement_id?: string | null
}): Promise<ResumeDetail> {
  const body = new FormData()
  body.append('display_name', payload.display_name)
  body.append('template', payload.template || 'classic')
  if (payload.target_job_id) body.append('target_job_id', payload.target_job_id)
  if (payload.target_announcement_id) {
    body.append('target_announcement_id', payload.target_announcement_id)
  }
  body.append('file', payload.file)
  const response = await apiClient.post<ResumeDetail>('/resumes/import/upload', body)
  return response.data
}

export async function createResumeFromDocument(payload: {
  document_id: string
  title?: string
  template?: ResumeTemplate
  target_job_id?: string | null
  target_announcement_id?: string | null
}): Promise<ResumeDetail> {
  const response = await apiClient.post<ResumeDetail>('/resumes/from-document', payload)
  return response.data
}

export async function createManualResume(
  payload: ResumeManualCreateInput,
): Promise<ResumeDetail> {
  const response = await apiClient.post<ResumeDetail>('/resumes/manual', payload)
  return response.data
}

export async function updateResume(
  resumeId: string,
  payload: ResumeUpdateInput,
): Promise<ResumeDetail> {
  const response = await apiClient.patch<ResumeDetail>(`/resumes/${resumeId}`, payload)
  return response.data
}

export async function reparseResume(resumeId: string): Promise<ResumeDetail> {
  const response = await apiClient.post<ResumeDetail>(`/resumes/${resumeId}/reparse`)
  return response.data
}

export async function deleteResume(resumeId: string): Promise<void> {
  await apiClient.delete(`/resumes/${resumeId}`)
}

export async function exportResume(
  resumeId: string,
  format: 'markdown' | 'html',
): Promise<string> {
  const response = await apiClient.get<string>(`/resumes/${resumeId}/export`, {
    params: { format },
    responseType: 'text',
    transformResponse: [(data) => data],
  })
  return response.data
}

export async function optimizeResume(
  resumeId: string,
  payload: ResumeOptimizeInput,
): Promise<ResumeOptimization> {
  const response = await apiClient.post<ResumeOptimization>(
    `/resumes/${resumeId}/optimizations`,
    payload,
  )
  return response.data
}

export async function listResumeOptimizations(
  resumeId: string,
): Promise<ResumeOptimizationListResponse> {
  const response = await apiClient.get<ResumeOptimizationListResponse>(
    `/resumes/${resumeId}/optimizations`,
  )
  return response.data
}

export async function getResumeOptimization(
  resumeId: string,
  optimizationId: string,
): Promise<ResumeOptimization> {
  const response = await apiClient.get<ResumeOptimization>(
    `/resumes/${resumeId}/optimizations/${optimizationId}`,
  )
  return response.data
}

export async function applyResumeOptimization(
  resumeId: string,
  optimizationId: string,
  suggestionIds: string[] = [],
): Promise<ResumeApplyResult> {
  const response = await apiClient.post<ResumeApplyResult>(
    `/resumes/${resumeId}/optimizations/${optimizationId}/apply`,
    { suggestion_ids: suggestionIds },
  )
  return response.data
}

export async function revertResumeOptimization(
  resumeId: string,
  optimizationId: string,
): Promise<ResumeDetail> {
  const response = await apiClient.post<ResumeDetail>(
    `/resumes/${resumeId}/optimizations/${optimizationId}/revert`,
  )
  return response.data
}

export async function discardResumeOptimization(
  resumeId: string,
  optimizationId: string,
): Promise<ResumeOptimization> {
  const response = await apiClient.post<ResumeOptimization>(
    `/resumes/${resumeId}/optimizations/${optimizationId}/discard`,
  )
  return response.data
}
