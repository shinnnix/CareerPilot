import type { ApplicationStatus } from './applications'

export type AgentIntent =
  | 'job_search'
  | 'match_report'
  | 'skill_gap'
  | 'create_application'
  | 'update_application'

export type AgentRunStatus =
  | 'running'
  | 'waiting_confirmation'
  | 'completed'
  | 'failed'
  | 'cancelled'

export interface AgentRun {
  id: string
  intent: AgentIntent | null
  status: AgentRunStatus
  current_node: string
  step_count: number
  max_steps: number
  input_payload: Record<string, unknown>
  checkpoint_state: Record<string, unknown>
  pending_action: Record<string, unknown> | null
  result: Record<string, unknown> | null
  last_error: string | null
  created_at: string
  updated_at: string
}

export interface AgentRunInput {
  message: string
  intent?: AgentIntent
  query?: string
  city?: string
  job_id?: string
  resume_document_id?: string
  application_id?: string
  application_status?: ApplicationStatus
  max_steps?: number
}

export interface AgentEventItem {
  id: string
  event: string
  data: Record<string, unknown>
}
