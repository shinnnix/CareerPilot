import type { DocumentType } from './documents'

export type RetrievalMode = 'keyword' | 'dense' | 'hybrid' | 'rerank'

export interface SearchHit {
  chunk_id: string
  document_id: string
  document_name: string
  document_type: DocumentType
  section_path: string[]
  chunk_type: string
  content: string
  expanded_content: string | null
  keyword_score: number | null
  dense_score: number | null
  fusion_score: number | null
  rerank_score: number | null
}

export interface SearchResponse {
  query: string
  mode: RetrievalMode
  embedding_model: string
  reranker_model: string | null
  latency_ms: number
  candidates_considered: number
  items: SearchHit[]
}

export interface MatchReport {
  job_id: string
  resume_document_id: string
  eligible: boolean
  total_score: number
  hard_gate: {
    passed: boolean
    checks: Record<string, boolean>
    reasons: string[]
  }
  breakdown: {
    required_skill_coverage: number
    preferred_skill_coverage: number
    experience_semantic_score: number
    project_domain_score: number
    preference_score: number
    freshness_score: number
  }
  matched_required_skills: string[]
  missing_required_skills: string[]
  matched_preferred_skills: string[]
  missing_preferred_skills: string[]
  evidence: SearchHit[]
  scoring_version: string
}
