export interface JobRowCompany {
  name: string
  type: string | null
  scale: string | null
  industry: string | null
}

export interface DeadlineInfo {
  text: string | null
  at: string | null
}

export interface JobSourceInfo {
  kind: string
  name: string | null
  url: string | null
}

export interface JobRow {
  id: string
  title: string
  company: JobRowCompany
  recruitment_type: string | null
  target_cohort: string | null
  locations: string[]
  positions_preview: string
  position_count: number
  published_at: string | null
  updated_at: string
  deadline: DeadlineInfo
  mark_status: string
  mark_status_label: string
  mark_note: string | null
  stage_summary: Record<string, number>
  application_ids: string[]
  applied_position_count: number
  source: JobSourceInfo
}

export interface JobCatalogResponse {
  items: JobRow[]
  page: number
  page_size: number
  total: number
  page_count: number
}

export type JobSort = 'updated_desc' | 'published_desc' | 'deadline_asc'

export interface JobCatalogParams {
  keyword?: string
  company?: string
  status?: string
  company_type?: string
  recruitment_type?: string
  target_cohort?: string
  location?: string
  job_category?: string
  sort?: JobSort
  page?: number
  page_size?: number
}

export interface JobFilters {
  keyword: string
  company: string
  status: string
  company_type: string
  recruitment_type: string
  target_cohort: string
  location: string
  job_category: string
  sort: JobSort
  page: number
  page_size: number
}

export interface FacetOption {
  value: string
  label: string
  count: number
}

export interface JobFacets {
  company_types: FacetOption[]
  recruitment_types: FacetOption[]
  target_cohorts: FacetOption[]
  locations: FacetOption[]
  job_categories: FacetOption[]
  statuses: FacetOption[]
}

export interface JobPositionItem {
  id: string
  title: string
  category: string | null
  city: string | null
  education: string | null
  headcount: string | null
  jd_text: string | null
  sort_order: number
  application_id: string | null
  application_status: string | null
  application_status_label: string | null
}

export interface JobAnnouncement {
  id: string
  title: string
  company: JobRowCompany
  recruitment_type: string | null
  target_cohort: string | null
  locations: string[]
  positions_text: string | null
  announcement_url: string | null
  source_url: string | null
  source_channel: string
  published_at: string | null
  deadline: DeadlineInfo
  raw_text: string
  apply_method: {
    emails?: string[]
    links?: string[]
    note?: string | null
  }
  snapshot_at: string | null
  status: string
  visibility: string
  mark_status: string
  mark_status_label: string
  mark_note: string | null
  positions: JobPositionItem[]
  source: JobSourceInfo
  created_at: string
  updated_at: string
}

export interface JobImportDraft {
  title: string | null
  company_name: string | null
  recruitment_type: string | null
  target_cohort: string | null
  locations: string[]
  positions: string[]
  deadline_text: string | null
  deadline_at: string | null
  published_at: string | null
  apply_method: {
    emails?: string[]
    links?: string[]
    note?: string | null
  }
  confidence: Record<string, string>
  /** Rule vs LLM disagreements; the rule value wins, both are shown for review. */
  needs_review?: boolean
  alternatives?: Record<string, { rule?: unknown; llm?: unknown }>
}

export interface JobImportRecord {
  id: string
  mode: 'text' | 'file' | 'article_url'
  source_url: string | null
  status: string
  llm_used: boolean
  error: string | null
  parsed: JobImportDraft
  raw_snapshot: string
  created_at: string
}

export interface JobImportConfirmInput {
  title: string
  company_name: string
  company_type?: string | null
  company_scale?: string | null
  industry?: string | null
  recruitment_type?: string | null
  target_cohort?: string | null
  locations: string[]
  positions: { title: string; city?: string | null; category?: string | null }[]
  deadline_text?: string | null
  deadline_at?: string | null
  published_at?: string | null
  announcement_url?: string | null
  apply_method?: Record<string, unknown>
  raw_text?: string | null
}

export interface JobMarkInput {
  status: 'deferred' | 'none'
  note?: string | null
}

export interface JobMarkResult {
  announcement_id: string
  mark_status: string
  mark_status_label: string
  note: string | null
}

export interface JobColumnOption {
  key: string
  label: string
  default: boolean
}

export interface JobTablePreference {
  table_key: string
  visible_columns: string[]
  available_columns: JobColumnOption[]
}

export interface CreateApplicationsInput {
  announcement_id: string
  position_ids: string[]
  status?: string
  applied_at?: string | null
  channel?: string | null
  contact_name?: string | null
  contact_info?: string | null
  notes?: string | null
}

export const JOB_COLUMN_LABELS: Record<string, string> = {
  company_name: '公司名称',
  company_type: '公司类型',
  recruitment_type: '招聘类型',
  target_cohort: '招聘对象',
  location: '工作地点',
  positions: '岗位',
  updated_at: '更新时间',
  deadline: '投递截止',
  announcement: '招聘公告',
  company_scale: '公司规模',
  mark_status: '状态',
}

export const DEFAULT_JOB_COLUMNS = [
  'company_name',
  'company_type',
  'recruitment_type',
  'target_cohort',
  'location',
  'positions',
  'updated_at',
  'deadline',
  'announcement',
  'mark_status',
]

export const COMPANY_TYPES = ['民企', '国企', '外企', '央企', '事业单位']
export const RECRUITMENT_TYPES = ['秋招', '春招', '社招', '实习', '补录']

// ---------------------------------------------------------------------------
// Module 2 — application records (plan §3.1 – §3.6)
// ---------------------------------------------------------------------------

export type ApplicationSort = 'applied_desc' | 'updated_desc' | 'follow_up_asc'
export type StageKey = 'written_test' | 'interview' | 'offer'

export interface ApplicationRow {
  id: string
  company_name: string
  position_title: string
  status: string
  status_label: string
  is_terminal: boolean
  applied_at: string | null
  follow_up_at: string | null
  follow_up_due: boolean
  channel: string | null
  contact_name: string | null
  contact_info: string | null
  link: string | null
  notes: string | null
  closed_reason: string | null
  rejected_stage: string | null
  announcement_id: string | null
  position_id: string | null
  job_id: string | null
  resume_id?: string | null
  resume_version_id?: string | null
  row_version: number
  created_at: string
  updated_at: string
}

export interface ApplicationListParams {
  keyword?: string
  status?: string
  sort?: ApplicationSort
  page?: number
  page_size?: number
}

export interface ApplicationFilters {
  keyword: string
  status: string
  sort: ApplicationSort
  page: number
  page_size: number
}

export interface ApplicationListResponse {
  items: ApplicationRow[]
  page: number
  page_size: number
  total: number
  page_count: number
  status_counts: Record<string, number>
}

export interface ApplicationEventItem {
  id: string
  event_type: string
  from_status: string | null
  to_status: string | null
  note: string | null
  created_at: string
}

export interface ApplicationStageDetail {
  id: string
  stage: StageKey
  stage_label: string
  payload: Record<string, unknown>
  occurred_at: string | null
  created_at: string
  updated_at: string
}

export interface ResumeVersionSummary {
  id: string
  resume_id: string
  version_no: number
  source: 'locked' | 'applied_optimization' | 'manual'
  note: string | null
  created_at: string
}

export interface ResumeVersionDetail extends ResumeVersionSummary {
  head: import('./resumes').ResumeHead
  sections: import('./resumes').ResumeSection[]
}

export interface ReminderItem {
  id: string
  application_id: string | null
  rule_type: string
  title: string
  body: string | null
  due_at: string
  status: 'pending' | 'done' | 'dismissed'
  snoozed_until: string | null
  done_at: string | null
  created_at: string
}

export interface ReminderListResponse {
  items: ReminderItem[]
  total: number
  pending: number
  due_now: number
}

export interface ReminderSummaryResponse {
  pending: number
  due_now: number
}

export interface JobMarkBatchInput {
  announcement_ids: string[]
  status: 'deferred' | 'none'
  note?: string | null
}

export interface ApplicationRecord extends ApplicationRow {
  events: ApplicationEventItem[]
  stage_details: ApplicationStageDetail[]
  allowed_transitions: string[]
  recommended_missing: string[]
  resume_version: ResumeVersionSummary | null
}

export interface ApplicationCreateInput {
  announcement_id?: string | null
  position_ids?: string[]
  company_name?: string | null
  position_title?: string | null
  status?: string
  applied_at?: string | null
  follow_up_at?: string | null
  channel?: string | null
  contact_name?: string | null
  contact_info?: string | null
  link?: string | null
  notes?: string | null
  allow_duplicate?: boolean
}

export interface ApplicationUpdateInput {
  status?: string
  applied_at?: string | null
  follow_up_at?: string | null
  channel?: string | null
  contact_name?: string | null
  contact_info?: string | null
  link?: string | null
  notes?: string | null
  closed_reason?: string | null
  rejected_stage?: string | null
  event_note?: string | null
  row_version: number
}

export interface ApplicationMetricsResponse {
  total: number
  by_status: Record<string, number>
  due_follow_ups: number
  terminal: number
  active: number
}

export interface InterviewRoundInput {
  index: number
  scheduled_at?: string | null
  completed_at?: string | null
  format?: 'online' | 'onsite' | 'phone' | null
  interviewer?: string | null
  questions?: string[]
  notes?: string | null
  self_rating?: number | null
}

export const APPLICATION_STAGE_LABELS: Record<StageKey, string> = {
  written_test: '笔试详情',
  interview: '面试详情',
  offer: 'Offer 详情',
}
