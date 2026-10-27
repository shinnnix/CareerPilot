import {
  ALLOWED_TRANSITIONS,
  APPLICATION_STATUS_LABELS,
  TERMINAL_STATUSES,
  type ApplicationStatus,
} from '@/types/applications'

export type TagType = 'success' | 'warning' | 'info' | 'danger' | 'primary'

/** Tag colours: offer = success, rejected = danger, in-flight = warning. */
export function statusTagType(status: string): TagType {
  if (status === 'offer') return 'success'
  if (status === 'rejected') return 'danger'
  if (status === 'applied') return 'primary'
  if (status === 'written_test' || status === 'interview_done') return 'warning'
  return 'info'
}

export function statusLabel(status: string): string {
  return APPLICATION_STATUS_LABELS[status as ApplicationStatus] ?? status
}

export function isTerminal(status: string): boolean {
  return (TERMINAL_STATUSES as string[]).includes(status)
}

export function nextStatuses(status: string): ApplicationStatus[] {
  return ALLOWED_TRANSITIONS[status as ApplicationStatus] ?? []
}

/** ``YYYY-MM-DD`` for date-only display; empty values render as a dash. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  return value.slice(0, 10)
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  const pad = (input: number) => String(input).padStart(2, '0')
  return (
    `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())} ` +
    `${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`
  )
}

/** Today in the browser's timezone, as ``YYYY-MM-DD``. */
export function today(): string {
  const now = new Date()
  const pad = (input: number) => String(input).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

/** ``YYYY-MM-DD`` → ISO datetime at UTC midnight, for the API. */
export function toIsoDate(value: string | null | undefined): string | null {
  if (!value) return null
  return value.length === 10 ? `${value}T00:00:00+00:00` : value
}

export const EVENT_LABELS: Record<string, string> = {
  created: '创建记录',
  status_changed: '状态变更',
  status_corrected: '修正状态',
  note_added: '添加备注',
  stage_detail_updated: '更新阶段详情',
  stage_detail_deleted: '删除阶段详情',
  resume_version_locked: '锁定简历版本',
  deleted: '删除记录',
}

export function eventLabel(eventType: string): string {
  return EVENT_LABELS[eventType] ?? eventType
}
