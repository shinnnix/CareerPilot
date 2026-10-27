/**
 * Browser-local application profile (plan §5.1).
 *
 * Nothing here is ever sent to the backend for storage: the profile lives in the
 * user's browser and is only passed to `autofill-plan` for a single mapping run.
 */

export const PROFILE_SCHEMA_VERSION = 1
export const PROFILE_STORAGE_KEY = 'careerpilot.profile.v1'
export const PROFILE_SYNC_KEY = 'careerpilot.profile.v1.sync'
export const EXTENSION_ID_KEY = 'careerpilot.extension.v1'

/** Fields that must never travel over any sync channel unless explicitly asked. */
export const SENSITIVE_PATHS = ['basic.idNumber', 'basic.studentId'] as const

export interface ProfileBasic {
  name: string
  gender: string
  birthday: string
  phone: string
  email: string
  wechat: string
  city: string
  hometown: string
  politicalStatus: string
  /** Sensitive: local only, never filled by default. */
  idNumber: string
  /** Sensitive: local only, never filled by default. */
  studentId: string
}

export interface ProfileEducation {
  id: string
  school: string
  major: string
  degree: string
  startDate: string
  endDate: string
  gpa: string
}

export interface ProfileExperience {
  id: string
  company: string
  title: string
  startDate: string
  endDate: string
  description: string
}

export interface ProfileProject {
  id: string
  name: string
  role: string
  startDate: string
  endDate: string
  description: string
  link: string
}

export interface ProfileSkills {
  skills: string[]
  certificates: string[]
  languages: string[]
}

export interface ProfilePreferences {
  cities: string[]
  roles: string[]
  availableFrom: string
  daysPerWeek: string
  monthsAvailable: string
  salaryExpectation: string
}

export interface ProfileLinks {
  github: string
  portfolio: string
  blog: string
  linkedin: string
}

export interface CareerProfile {
  schemaVersion: number
  /** Monotonic counter used to resolve sync conflicts (newer wins). */
  profileVersion: number
  updatedAt: string
  basic: ProfileBasic
  education: ProfileEducation[]
  experience: ProfileExperience[]
  projects: ProfileProject[]
  skills: ProfileSkills
  preferences: ProfilePreferences
  links: ProfileLinks
  /** Field path (`basic.email`) → ISO timestamp of the user's confirmation. */
  confirmedAt: Record<string, string>
}

export type SyncChannel = 'direct' | 'storage' | 'json' | 'none'

export const SYNC_CHANNEL_LABELS: Record<SyncChannel, string> = {
  direct: '① 直连扩展',
  storage: '② 读取页面存储',
  json: '③ 导出 JSON 粘贴',
  none: '未检测到扩展',
}

export const SYNC_CHANNEL_HINTS: Record<SyncChannel, string> = {
  direct: '通过扩展消息通道直接推送，带 ack 回执',
  storage: '扩展已注入本页，可读取精简快照（不含敏感字段）',
  json: '导出 JSON 后在插件弹窗中粘贴',
  none: '安装扩展后回到本页刷新，即可自动升级通道',
}

export const PROFILE_FIELD_LABELS: Record<string, string> = {
  'basic.name': '姓名',
  'basic.gender': '性别',
  'basic.birthday': '生日',
  'basic.phone': '手机',
  'basic.email': '邮箱',
  'basic.wechat': '微信',
  'basic.city': '现居城市',
  'basic.hometown': '籍贯',
  'basic.politicalStatus': '政治面貌',
  'basic.idNumber': '身份证号（仅本地）',
  'basic.studentId': '学号（仅本地）',
}

export function emptyProfile(): CareerProfile {
  return {
    schemaVersion: PROFILE_SCHEMA_VERSION,
    profileVersion: 1,
    updatedAt: new Date().toISOString(),
    basic: {
      name: '',
      gender: '',
      birthday: '',
      phone: '',
      email: '',
      wechat: '',
      city: '',
      hometown: '',
      politicalStatus: '',
      idNumber: '',
      studentId: '',
    },
    education: [],
    experience: [],
    projects: [],
    skills: { skills: [], certificates: [], languages: [] },
    preferences: {
      cities: [],
      roles: [],
      availableFrom: '',
      daysPerWeek: '',
      monthsAvailable: '',
      salaryExpectation: '',
    },
    links: { github: '', portfolio: '', blog: '', linkedin: '' },
    confirmedAt: {},
  }
}

export function isSensitivePath(path: string): boolean {
  return (SENSITIVE_PATHS as readonly string[]).includes(path)
}

/**
 * Payload accepted by `POST /workspace/applications/{id}/autofill-plan`.
 *
 * Sensitive fields are stripped unless `includeSensitive` is set, matching the
 * "only local, opt-in" rule from plan §5.1.
 */
export function toAutofillProfile(
  profile: CareerProfile,
  includeSensitive = false,
): Record<string, unknown> {
  const basic: Record<string, unknown> = {
    name: profile.basic.name,
    gender: profile.basic.gender,
    birthday: profile.basic.birthday,
    phone: profile.basic.phone,
    email: profile.basic.email,
    wechat: profile.basic.wechat,
    city: profile.basic.city,
    hometown: profile.basic.hometown,
    politicalStatus: profile.basic.politicalStatus,
  }
  if (includeSensitive) {
    basic.idNumber = profile.basic.idNumber
    basic.studentId = profile.basic.studentId
  }
  return {
    basic,
    education: profile.education,
    experience: profile.experience,
    projects: profile.projects,
    skills: profile.skills,
    preferences: profile.preferences,
    links: profile.links,
  }
}

/** Trimmed copy used by sync channel ② (always free of sensitive fields). */
export function toSyncSnapshot(profile: CareerProfile): Record<string, unknown> {
  return {
    schemaVersion: PROFILE_SCHEMA_VERSION,
    profileVersion: profile.profileVersion,
    updatedAt: profile.updatedAt,
    source: 'page',
    fields: toAutofillProfile(profile, false),
  }
}

export interface ProfileExportOptions {
  includeSensitive?: boolean
}

export function exportProfile(
  profile: CareerProfile,
  options: ProfileExportOptions = {},
): string {
  return JSON.stringify(
    {
      schemaVersion: PROFILE_SCHEMA_VERSION,
      profileVersion: profile.profileVersion,
      updatedAt: profile.updatedAt,
      ...toAutofillProfile(profile, options.includeSensitive ?? false),
    },
    null,
    2,
  )
}

export interface ProfileImportResult {
  ok: boolean
  profile?: CareerProfile
  error?: string
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : value == null ? '' : String(value)
}

function asStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map(asString).filter(Boolean) : []
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

/** Accepts exported JSON or a pasted plugin payload; never throws. */
export function importProfile(raw: string): ProfileImportResult {
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    return { ok: false, error: '不是合法的 JSON 文本' }
  }
  const root = asRecord(parsed)
  // A plugin payload wraps the fields under `fields`.
  const source = Object.keys(asRecord(root.fields)).length ? asRecord(root.fields) : root
  const schemaVersion = Number(root.schemaVersion ?? PROFILE_SCHEMA_VERSION)
  if (!Number.isFinite(schemaVersion) || schemaVersion > PROFILE_SCHEMA_VERSION) {
    return { ok: false, error: `不支持的 schemaVersion：${root.schemaVersion}` }
  }
  const base = emptyProfile()
  const basic = asRecord(source.basic)
  const preferences = asRecord(source.preferences)
  const links = asRecord(source.links)
  const skills = asRecord(source.skills)
  const profile: CareerProfile = {
    ...base,
    profileVersion: Math.max(1, Number(root.profileVersion ?? 1) || 1),
    updatedAt: asString(root.updatedAt) || new Date().toISOString(),
    basic: {
      name: asString(basic.name),
      gender: asString(basic.gender),
      birthday: asString(basic.birthday),
      phone: asString(basic.phone),
      email: asString(basic.email),
      wechat: asString(basic.wechat),
      city: asString(basic.city),
      hometown: asString(basic.hometown),
      politicalStatus: asString(basic.politicalStatus),
      idNumber: asString(basic.idNumber),
      studentId: asString(basic.studentId),
    },
    education: (Array.isArray(source.education) ? source.education : []).map((item) => {
      const row = asRecord(item)
      return {
        id: asString(row.id) || crypto.randomUUID(),
        school: asString(row.school),
        major: asString(row.major),
        degree: asString(row.degree),
        startDate: asString(row.startDate),
        endDate: asString(row.endDate),
        gpa: asString(row.gpa),
      }
    }),
    experience: (Array.isArray(source.experience) ? source.experience : []).map((item) => {
      const row = asRecord(item)
      return {
        id: asString(row.id) || crypto.randomUUID(),
        company: asString(row.company),
        title: asString(row.title),
        startDate: asString(row.startDate),
        endDate: asString(row.endDate),
        description: asString(row.description),
      }
    }),
    projects: (Array.isArray(source.projects) ? source.projects : []).map((item) => {
      const row = asRecord(item)
      return {
        id: asString(row.id) || crypto.randomUUID(),
        name: asString(row.name),
        role: asString(row.role),
        startDate: asString(row.startDate),
        endDate: asString(row.endDate),
        description: asString(row.description),
        link: asString(row.link),
      }
    }),
    skills: {
      skills: asStringList(skills.skills),
      certificates: asStringList(skills.certificates),
      languages: asStringList(skills.languages),
    },
    preferences: {
      cities: asStringList(preferences.cities),
      roles: asStringList(preferences.roles),
      availableFrom: asString(preferences.availableFrom),
      daysPerWeek: asString(preferences.daysPerWeek),
      monthsAvailable: asString(preferences.monthsAvailable),
      salaryExpectation: asString(preferences.salaryExpectation),
    },
    links: {
      github: asString(links.github),
      portfolio: asString(links.portfolio),
      blog: asString(links.blog),
      linkedin: asString(links.linkedin),
    },
  }
  return { ok: true, profile }
}
