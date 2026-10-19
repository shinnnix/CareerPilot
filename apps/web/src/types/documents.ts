export type DocumentType = 'resume' | 'job_description' | 'learning_note' | 'other'
export type ParseStatus = 'parsed' | 'failed'
export type ReviewStatus = 'pending' | 'confirmed'

export interface ExtractedDocumentData {
  title: string | null
  company_name: string | null
  city: string | null
  email: string | null
  phone: string | null
  skills: string[]
  section_titles: string[]
  desired_cities: string[]
  available_days_per_week: number | null
  available_months: number | null
}

export interface DocumentSummary {
  id: string
  display_name: string
  file_name: string | null
  mime_type: string
  document_type: DocumentType
  content_hash: string
  source_size_bytes: number
  parse_status: ParseStatus
  parse_version: string
  parse_confidence: string
  review_status: ReviewStatus
  prompt_injection_detected: boolean
  security_flags: string[]
  index_version: string
  chunk_count: number
  created_at: string
  updated_at: string
}

export interface DocumentDetail extends DocumentSummary {
  raw_text: string
  extracted_data: ExtractedDocumentData
  confirmed_at: string | null
}

export interface DocumentChunk {
  id: string
  document_id: string
  position: number
  section_path: string[]
  chunk_type: string
  content: string
  contextualized_content: string
  char_count: number
  estimated_token_count: number
  content_hash: string
  parser_version: string
  index_version: string
  embedding_model: string | null
}

export interface DocumentListResponse {
  items: DocumentSummary[]
  page: number
  page_size: number
  total: number
}

export interface ChunkListResponse {
  items: DocumentChunk[]
  total: number
}

export interface TextDocumentInput {
  display_name: string
  document_type: DocumentType
  raw_text: string
}

export interface DocumentCorrectionInput {
  extracted_data: ExtractedDocumentData
}
