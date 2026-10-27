import { apiClient } from './client'
import type {
  ApplicationCreateInput,
  ApplicationListParams,
  ApplicationListResponse,
  ApplicationMetricsResponse,
  ApplicationRecord,
  ApplicationStageDetail,
  ApplicationUpdateInput,
  CreateApplicationsInput,
  JobAnnouncement,
  JobCatalogParams,
  JobCatalogResponse,
  JobFacets,
  JobImportConfirmInput,
  JobImportRecord,
  JobMarkBatchInput,
  JobMarkInput,
  JobMarkResult,
  JobTablePreference,
  ReminderItem,
  ReminderListResponse,
  ReminderSummaryResponse,
  ResumeVersionSummary,
  StageKey,
} from '@/types/workspace'
import type { ApplicationSummary } from '@/types/applications'

export async function listJobCatalog(params: JobCatalogParams): Promise<JobCatalogResponse> {
  const response = await apiClient.get<JobCatalogResponse>('/workspace/jobs', { params })
  return response.data
}

export async function getJobFacets(): Promise<JobFacets> {
  const response = await apiClient.get<JobFacets>('/workspace/jobs/filters')
  return response.data
}

export async function getJobAnnouncement(announcementId: string): Promise<JobAnnouncement> {
  const response = await apiClient.get<JobAnnouncement>(`/workspace/jobs/${announcementId}`)
  return response.data
}

export async function markJob(
  announcementId: string,
  payload: JobMarkInput,
): Promise<JobMarkResult> {
  const response = await apiClient.patch<JobMarkResult>(
    `/workspace/jobs/${announcementId}/mark`,
    payload,
  )
  return response.data
}

export async function markJobsBatch(payload: JobMarkBatchInput): Promise<JobMarkResult[]> {
  const response = await apiClient.patch<JobMarkResult[]>('/workspace/jobs/marks', payload)
  return response.data
}

export async function importJobText(payload: {
  raw_text: string
  source_name?: string | null
  source_url?: string | null
}): Promise<JobImportRecord> {
  const response = await apiClient.post<JobImportRecord>('/workspace/jobs/import/text', payload)
  return response.data
}

export async function importJobFile(file: File): Promise<JobImportRecord> {
  const form = new FormData()
  form.append('file', file)
  const response = await apiClient.post<JobImportRecord>('/workspace/jobs/import/file', form)
  return response.data
}

export async function importJobArticle(payload: {
  url: string
  source_name?: string | null
}): Promise<JobImportRecord> {
  const response = await apiClient.post<JobImportRecord>(
    '/workspace/jobs/import/article',
    payload,
  )
  return response.data
}

export async function confirmJobImport(
  importId: string,
  payload: JobImportConfirmInput,
): Promise<JobAnnouncement> {
  const response = await apiClient.post<JobAnnouncement>(
    `/workspace/jobs/imports/${importId}/confirm`,
    payload,
  )
  return response.data
}

export async function deleteJobImport(importId: string): Promise<void> {
  await apiClient.delete(`/workspace/jobs/imports/${importId}`)
}

export async function getJobTablePreference(): Promise<JobTablePreference> {
  const response = await apiClient.get<JobTablePreference>('/workspace/preferences/job-table')
  return response.data
}

export async function saveJobTablePreference(
  visibleColumns: string[],
): Promise<JobTablePreference> {
  const response = await apiClient.put<JobTablePreference>('/workspace/preferences/job-table', {
    visible_columns: visibleColumns,
  })
  return response.data
}

export async function createApplications(
  payload: CreateApplicationsInput | ApplicationCreateInput,
): Promise<{ items: ApplicationSummary[]; total: number }> {
  const response = await apiClient.post<{ items: ApplicationSummary[]; total: number }>(
    '/workspace/applications',
    payload,
  )
  return response.data
}

/**
 * CSV export must go through the axios client so the Bearer token / demo header
 * is attached. A plain ``window.open(url)`` would 401 in real-auth deployments.
 */
export async function downloadJobCatalogCsv(params: JobCatalogParams): Promise<Blob> {
  const response = await apiClient.get('/workspace/jobs/export', {
    params,
    responseType: 'blob',
  })
  return response.data as Blob
}

// ---------------------------------------------------------------------------
// Module 2 — application records
// ---------------------------------------------------------------------------

export async function listApplicationRecords(
  params: ApplicationListParams,
): Promise<ApplicationListResponse> {
  const response = await apiClient.get<ApplicationListResponse>('/workspace/applications', {
    params,
  })
  return response.data
}

export async function getApplicationRecord(applicationId: string): Promise<ApplicationRecord> {
  const response = await apiClient.get<ApplicationRecord>(
    `/workspace/applications/${applicationId}`,
  )
  return response.data
}

export async function updateApplicationRecord(
  applicationId: string,
  payload: ApplicationUpdateInput,
): Promise<ApplicationRecord> {
  const response = await apiClient.patch<ApplicationRecord>(
    `/workspace/applications/${applicationId}`,
    payload,
  )
  return response.data
}

export async function deleteApplicationRecord(applicationId: string): Promise<void> {
  await apiClient.delete(`/workspace/applications/${applicationId}`)
}

export async function getApplicationMetrics(): Promise<ApplicationMetricsResponse> {
  const response = await apiClient.get<ApplicationMetricsResponse>(
    '/workspace/applications/metrics',
  )
  return response.data
}

export async function listStageDetails(
  applicationId: string,
): Promise<ApplicationStageDetail[]> {
  const response = await apiClient.get<ApplicationStageDetail[]>(
    `/workspace/applications/${applicationId}/stage-details`,
  )
  return response.data
}

export async function saveStageDetail(
  applicationId: string,
  stage: StageKey,
  payload: Record<string, unknown>,
  occurredAt?: string | null,
): Promise<ApplicationStageDetail> {
  const response = await apiClient.put<ApplicationStageDetail>(
    `/workspace/applications/${applicationId}/stage-details/${stage}`,
    { payload, occurred_at: occurredAt ?? null },
  )
  return response.data
}

export async function deleteStageDetail(applicationId: string, stage: StageKey): Promise<void> {
  await apiClient.delete(`/workspace/applications/${applicationId}/stage-details/${stage}`)
}

/** Authenticated counterpart of the applications CSV export (see above). */
export async function downloadApplicationCsv(params: ApplicationListParams): Promise<Blob> {
  const response = await apiClient.get('/workspace/applications/export', {
    params,
    responseType: 'blob',
  })
  return response.data as Blob
}

/** Lock (or re-lock) the resume snapshot attached to an application. */
export async function lockApplicationResume(
  applicationId: string,
  payload: { resume_id?: string | null; note?: string | null } = {},
): Promise<ApplicationRecord> {
  const response = await apiClient.post<ApplicationRecord>(
    `/workspace/applications/${applicationId}/resume-version`,
    payload,
  )
  return response.data
}

export async function listApplicationResumeVersions(
  resumeId: string,
): Promise<{ items: ResumeVersionSummary[]; total: number }> {
  const response = await apiClient.get<{ items: ResumeVersionSummary[]; total: number }>(
    `/resumes/${resumeId}/versions`,
  )
  return response.data
}

export async function getResumeVersionDetail(
  resumeId: string,
  versionNo: number,
): Promise<import('@/types/workspace').ResumeVersionDetail> {
  const response = await apiClient.get<import('@/types/workspace').ResumeVersionDetail>(
    `/resumes/${resumeId}/versions/${versionNo}`,
  )
  return response.data
}

// ---------------------------------------------------------------------------
// Reminder inbox
// ---------------------------------------------------------------------------

export async function listReminders(params: {
  status?: 'pending' | 'done' | 'dismissed'
  include_snoozed?: boolean
} = {}): Promise<ReminderListResponse> {
  const response = await apiClient.get<ReminderListResponse>('/workspace/reminders', {
    params,
  })
  return response.data
}

export async function getReminderSummary(): Promise<ReminderSummaryResponse> {
  const response = await apiClient.get<ReminderSummaryResponse>(
    '/workspace/reminders/summary',
  )
  return response.data
}

export async function completeReminder(reminderId: string): Promise<ReminderItem> {
  const response = await apiClient.post<ReminderItem>(
    `/workspace/reminders/${reminderId}/done`,
  )
  return response.data
}

export async function dismissReminder(reminderId: string): Promise<ReminderItem> {
  const response = await apiClient.post<ReminderItem>(
    `/workspace/reminders/${reminderId}/dismiss`,
  )
  return response.data
}

export async function snoozeReminder(
  reminderId: string,
  hours = 24,
): Promise<ReminderItem> {
  const response = await apiClient.post<ReminderItem>(
    `/workspace/reminders/${reminderId}/snooze`,
    { hours },
  )
  return response.data
}
