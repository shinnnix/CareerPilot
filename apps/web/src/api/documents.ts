import { apiClient } from './client'
import type {
  ChunkListResponse,
  DocumentCorrectionInput,
  DocumentDetail,
  DocumentListResponse,
  DocumentType,
  ReviewStatus,
  TextDocumentInput,
} from '@/types/documents'

export async function listDocuments(params: {
  document_type?: DocumentType
  review_status?: ReviewStatus
  page?: number
  page_size?: number
} = {}): Promise<DocumentListResponse> {
  const response = await apiClient.get<DocumentListResponse>('/documents', { params })
  return response.data
}

export async function importTextDocument(
  payload: TextDocumentInput,
): Promise<DocumentDetail> {
  const response = await apiClient.post<DocumentDetail>('/documents/text', payload)
  return response.data
}

export async function uploadDocument(payload: {
  display_name: string
  document_type: DocumentType
  file: File
}): Promise<DocumentDetail> {
  const body = new FormData()
  body.append('display_name', payload.display_name)
  body.append('document_type', payload.document_type)
  body.append('file', payload.file)
  const response = await apiClient.post<DocumentDetail>('/documents/upload', body)
  return response.data
}

export async function getDocument(documentId: string): Promise<DocumentDetail> {
  const response = await apiClient.get<DocumentDetail>(`/documents/${documentId}`)
  return response.data
}

export async function getDocumentChunks(documentId: string): Promise<ChunkListResponse> {
  const response = await apiClient.get<ChunkListResponse>(`/documents/${documentId}/chunks`)
  return response.data
}

export async function correctDocument(
  documentId: string,
  payload: DocumentCorrectionInput,
): Promise<DocumentDetail> {
  const response = await apiClient.patch<DocumentDetail>(`/documents/${documentId}`, payload)
  return response.data
}

export async function reindexDocument(documentId: string): Promise<DocumentDetail> {
  const response = await apiClient.post<DocumentDetail>(`/documents/${documentId}/reindex`)
  return response.data
}

export async function deleteDocument(documentId: string): Promise<void> {
  await apiClient.delete(`/documents/${documentId}`)
}

