export type ResumeTemplate = 'classic' | 'modern' | 'elegant' | 'compact'
export type ResumeSectionKey =
  | 'education'
  | 'experience'
  | 'project'
  | 'skill'
  | 'summary'
  | 'other'
export type ResumeSource = 'upload' | 'text' | 'manual'
export type OptimizationStatus = 'generated' | 'applied' | 'reverted' | 'discarded'
export type ResumeSuggestionKind =
  | 'rewrite_bullet'
  | 'add_bullet'
  | 'add_skill'
  | 'add_section'
  | 'gap_plan'
export type SuggestionPriority = 'high' | 'medium' | 'low'

export interface ResumeLink {
  label: string
  url: string
}

export interface ResumeHead {
  name: string | null
  target_title: string | null
  phone: string | null
  email: string | null
  city: string | null
  links: ResumeLink[]
}

export interface ResumeEntry {
  id: string
  title: string
  subtitle: string | null
  period: string | null
  bullets: string[]
}

export interface ResumeSection {
  id: string
  key: ResumeSectionKey
  title: string
  entries: ResumeEntry[]
}

export interface ResumeAnalysis {
  parser_version: string | null
  source_document_id: string | null
  detected_section_titles: string[]
  warnings: string[]
  confidence: number
  source_content_hash: string | null
}

export interface ResumeSummary {
  id: string
  title: string
  template: ResumeTemplate
  font_size: number
  target_job_id: string | null
  /** Job-catalog announcement target (module 1); preferred over target_job_id. */
  target_announcement_id: string | null
  source: ResumeSource
  content_version: number
  document_id: string | null
  candidate_name: string | null
  target_title: string | null
  section_count: number
  entry_count: number
  created_at: string
  updated_at: string
}

export interface ResumeDetail extends ResumeSummary {
  head: ResumeHead
  sections: ResumeSection[]
  analysis: ResumeAnalysis
  optimization_count: number
}

export interface ResumeListResponse {
  items: ResumeSummary[]
  page: number
  page_size: number
  total: number
}

export interface ResumeCitation {
  source_type:
    | 'resume_entry'
    | 'resume_section'
    | 'resume_head'
    | 'job'
    | 'announcement'
    | 'jd_document'
    | 'jd_text'
  source_id: string
  quote: string
}

export interface ResumeSuggestion {
  id: string
  kind: ResumeSuggestionKind
  section_id: string
  entry_id: string | null
  bullet_index: number | null
  title: string
  original: string | null
  proposed: string | null
  rationale: string
  keywords: string[]
  citations: ResumeCitation[]
  priority: SuggestionPriority
  confidence: number
  requires_new_fact: boolean
  applicable: boolean
}

export interface ResumeBreakdown {
  required_skill_coverage: number
  preferred_skill_coverage: number
  experience_semantic_score: number
  project_domain_score: number
  preference_score: number
  freshness_score: number
}

export interface ResumeHardGate {
  passed: boolean
  checks: Record<string, boolean>
  reasons: string[]
  unknowns: string[]
}

export interface ResumeMatchEvidence {
  section_id: string
  section_title: string
  entry_id: string | null
  text: string
}

export interface ResumeMatchReport {
  source: 'job' | 'document' | 'text' | 'announcement'
  job_id: string | null
  jd_document_id: string | null
  jd_title: string
  company_name: string | null
  city: string | null
  eligible: boolean
  total_score: number
  breakdown: ResumeBreakdown
  hard_gate: ResumeHardGate
  matched_required_skills: string[]
  missing_required_skills: string[]
  matched_preferred_skills: string[]
  missing_preferred_skills: string[]
  keyword_hits: string[]
  strengths: string[]
  gaps: string[]
  evidence: ResumeMatchEvidence[]
  scoring_version: string
}

export interface JdSnapshot {
  source: 'job' | 'document' | 'text' | 'announcement'
  job_id: string | null
  announcement_id: string | null
  document_id: string | null
  title: string
  company_name: string | null
  city: string | null
  required_skills: string[]
  preferred_skills: string[]
  internship_days_per_week: number | null
  internship_months: number | null
  raw_text_excerpt: string
}

export interface ResumeDraft {
  head: ResumeHead
  sections: ResumeSection[]
  applied_suggestion_ids: string[]
}

export interface ResumeOptimizationSummary {
  id: string
  resume_id: string
  status: OptimizationStatus
  job_id: string | null
  announcement_id: string | null
  jd_document_id: string | null
  jd_title: string
  total_score: number
  suggestion_count: number
  applicable_count: number
  created_at: string
  applied_at: string | null
}

export interface ResumeOptimization extends ResumeOptimizationSummary {
  jd: JdSnapshot
  match_report: ResumeMatchReport
  suggestions: ResumeSuggestion[]
  draft: ResumeDraft
  requires_review_count: number
  base_content_version: number
  applied_suggestion_ids: string[]
  generator_version: string
  prompt_injection_detected: boolean
  security_flags: string[]
}

export interface ResumeOptimizationListResponse {
  items: ResumeOptimizationSummary[]
  total: number
}

export interface ResumeApplyResult {
  resume: ResumeDetail
  optimization: ResumeOptimization
  applied_suggestion_ids: string[]
}

export interface ResumeOptimizeInput {
  job_id?: string
  announcement_id?: string
  jd_document_id?: string
  jd_text?: string
  focus?: string
}

export interface ResumeUpdateInput {
  title?: string
  template?: ResumeTemplate
  font_size?: number
  target_job_id?: string | null
  target_announcement_id?: string | null
  head?: ResumeHead
  sections?: ResumeSection[]
}

export interface ResumeTextImportInput {
  display_name: string
  raw_text: string
  template?: ResumeTemplate
  target_job_id?: string | null
  target_announcement_id?: string | null
}

export interface ResumeManualCreateInput {
  title: string
  template?: ResumeTemplate
  target_job_id?: string | null
  target_announcement_id?: string | null
  head?: ResumeHead
}
