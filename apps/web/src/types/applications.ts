export type ApplicationStatus =
  | 'saved'
  | 'preparing'
  | 'applied'
  | 'interview'
  | 'offer'
  | 'rejected'
  | 'withdrawn'

export interface ApplicationSummary {
  id: string
  job_id: string
  job_title: string
  company_name: string
  status: ApplicationStatus
  notes: string | null
  next_follow_up_at: string | null
  interview_feedback: string | null
  applied_at: string | null
  created_at: string
  updated_at: string
}

export interface ApplicationEvent {
  id: string
  event_type: string
  from_status: string | null
  to_status: string | null
  note: string | null
  created_at: string
}

export interface ApplicationDetail extends ApplicationSummary {
  events: ApplicationEvent[]
}

export interface ApplicationMetrics {
  total: number
  by_status: Record<ApplicationStatus, number>
  due_follow_ups: number
}

export interface Citation {
  source_type: string
  source_id: string
  quote: string
}

export interface ArtifactItem {
  text: string
  citations: Citation[]
}

export interface Artifact {
  id: string
  artifact_type: 'resume_bullets' | 'skill_gap_plan'
  content: ArtifactItem[]
  citation_valid: boolean
  generator_version: string
}

export interface PersonalizationResult {
  resume_bullets: Artifact
  skill_gap_plan: Artifact
}
