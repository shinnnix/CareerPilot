export type ApplicationStatus =
  | 'not_applied'
  | 'applied'
  | 'written_test'
  | 'interview_done'
  | 'offer'
  | 'rejected'
  | 'withdrawn'

/** Statuses describe completed milestones only — there is no "正在面试". */
export const APPLICATION_STATUS_LABELS: Record<ApplicationStatus, string> = {
  not_applied: '未投递',
  applied: '已投递',
  written_test: '已笔试',
  interview_done: '已面试',
  offer: '面试通过',
  rejected: '已挂',
  withdrawn: '已放弃',
}

export const APPLICATION_STATUSES: ApplicationStatus[] = [
  'not_applied',
  'applied',
  'written_test',
  'interview_done',
  'offer',
  'rejected',
  'withdrawn',
]

export const TERMINAL_STATUSES: ApplicationStatus[] = ['offer', 'rejected', 'withdrawn']

export const APPLICATION_CHANNELS = ['官网', '公众号邮箱', '网申链接', '内推', '招聘平台', '其他']

export const CLOSED_REASONS = ['HC 取消', '技能不匹配', '竞争失败', '流程过长', '薪资不符', '其他']

export const REJECTED_STAGES = ['简历', '笔试', '面试', '终面', '未知']

/** Forward-only transitions; mirrors the backend state machine (plan §3.2). */
export const ALLOWED_TRANSITIONS: Record<ApplicationStatus, ApplicationStatus[]> = {
  not_applied: ['applied'],
  applied: ['written_test', 'interview_done', 'offer', 'rejected', 'withdrawn'],
  written_test: ['interview_done', 'offer', 'rejected', 'withdrawn'],
  interview_done: ['offer', 'rejected', 'withdrawn'],
  offer: ['withdrawn'],
  // Mis-click correction: the backend logs these as `status_corrected`.
  rejected: ['applied'],
  withdrawn: ['applied'],
}

export interface ApplicationSummary {
  id: string
  job_id: string | null
  announcement_id?: string | null
  position_id?: string | null
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
