import { apiClient } from './client'
import type { MatchReport, RetrievalMode, SearchResponse } from '@/types/retrieval'

export async function indexKnowledgeBase(payload: {
  document_id?: string
  force?: boolean
} = {}): Promise<{ model_name: string; indexed_chunks: number; skipped_chunks: number }> {
  const response = await apiClient.post('/retrieval/index', payload)
  return response.data
}

export async function searchKnowledgeBase(payload: {
  query: string
  mode: RetrievalMode
  document_type?: string
  top_k?: number
  expand_parent?: boolean
}): Promise<SearchResponse> {
  const response = await apiClient.post<SearchResponse>('/retrieval/search', payload)
  return response.data
}

export async function buildMatchReport(
  jobId: string,
  resumeDocumentId: string,
): Promise<MatchReport> {
  const response = await apiClient.post<MatchReport>(`/jobs/${jobId}/match`, {
    resume_document_id: resumeDocumentId,
  })
  return response.data
}
