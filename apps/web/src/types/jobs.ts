export type EmploymentType = 'internship' | 'full_time' | 'part_time'
export type RemoteType = 'onsite' | 'hybrid' | 'remote'
export type JobStatus = 'active' | 'archived'

export interface Job {
  id: string
  title: string
  company_name: string
  city: string | null
  employment_type: EmploymentType
  remote_type: RemoteType
  salary_min: string | null
  salary_max: string | null
  internship_days_per_week: number | null
  internship_months: number | null
  required_skills: string[]
  preferred_skills: string[]
  source_url: string | null
  raw_text: string
  status: JobStatus
  created_at: string
  updated_at: string
}

export interface JobInput {
  title: string
  company_name: string
  city: string | null
  employment_type: EmploymentType
  remote_type: RemoteType
  salary_min: string | null
  salary_max: string | null
  internship_days_per_week: number | null
  internship_months: number | null
  required_skills: string[]
  preferred_skills: string[]
  source_url: string | null
  raw_text: string
  status: JobStatus
}

export type JobPatch = Partial<JobInput>

export interface JobListResponse {
  items: Job[]
  page: number
  page_size: number
  total: number
}

export interface JobSearchParams {
  keyword?: string
  city?: string
  status?: JobStatus
  page?: number
  page_size?: number
}

export interface ApiErrorPayload {
  code?: string
  message?: string
  details?: Record<string, unknown>
  request_id?: string
}

