/**
 * AI provider configuration (plan §5.3).
 *
 * Credentials never leave the browser except as a per-request `X-AI-Config`
 * header; the backend uses them in memory and discards them.
 */

export const AI_SCHEMA_VERSION = 1
export const AI_STORAGE_KEY = 'careerpilot.ai.v1'
export const AI_CONFIG_HEADER = 'X-AI-Config'

export type AiFormat = 'openai' | 'anthropic'
export type AiTask = 'chat' | 'extraction' | 'embedding' | 'rerank'

export const AI_FORMATS: AiFormat[] = ['openai', 'anthropic']

export const AI_FORMAT_LABELS: Record<AiFormat, string> = {
  openai: 'OpenAI 兼容格式',
  anthropic: 'Anthropic Messages 格式',
}

export const AI_FORMAT_HINTS: Record<AiFormat, string> = {
  openai: 'POST {base_url}/chat/completions，Authorization: Bearer。DeepSeek / 通义 / 智谱 / Ollama 都走这个格式',
  anthropic: 'POST {base_url}/v1/messages，x-api-key + anthropic-version。base_url 不要再带 /v1',
}

/** Anthropic has no embedding endpoint, so these tasks are OpenAI-only. */
export const OPENAI_ONLY_TASKS: AiTask[] = ['embedding', 'rerank']

export interface AiTaskMeta {
  key: AiTask
  label: string
  description: string
  required: boolean
}

export const AI_TASKS: AiTaskMeta[] = [
  {
    key: 'chat',
    label: '对话',
    description: '求职助手；未绑定时助手不可用，不会伪造回答',
    required: false,
  },
  {
    key: 'extraction',
    label: '结构化抽取',
    description: '公告/简历解析增强；未绑定时使用规则解析',
    required: false,
  },
  {
    key: 'embedding',
    label: '向量化',
    description: '仅 OpenAI 兼容或本地确定性实现',
    required: false,
  },
  {
    key: 'rerank',
    label: '重排',
    description: '仅 OpenAI 兼容或本地确定性实现，默认重叠重排',
    required: false,
  },
]

export const AI_TASK_LABELS: Record<AiTask, string> = {
  chat: '对话',
  extraction: '结构化抽取',
  embedding: '向量化',
  rerank: '重排',
}

export interface AiConfig {
  format: AiFormat
  baseUrl: string
  model: string
  apiKey: string
  temperature: number
  maxTokens: number
}

export interface AiSettings {
  schemaVersion: number
  updatedAt: string
  /** Per-task binding; a task without an entry falls back to the deterministic path. */
  tasks: Partial<Record<AiTask, AiConfig>>
}

export const AI_PRESETS: { label: string; format: AiFormat; baseUrl: string; model: string }[] = [
  { label: 'OpenAI', format: 'openai', baseUrl: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  { label: 'DeepSeek', format: 'openai', baseUrl: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  { label: '通义千问', format: 'openai', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus' },
  { label: '智谱 GLM', format: 'openai', baseUrl: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-flash' },
  { label: 'Ollama 本地', format: 'openai', baseUrl: 'http://127.0.0.1:11434/v1', model: 'qwen2.5:7b' },
  { label: 'Anthropic', format: 'anthropic', baseUrl: 'https://api.anthropic.com', model: 'claude-3-5-sonnet-latest' },
]

export function emptyAiConfig(format: AiFormat = 'openai'): AiConfig {
  return {
    format,
    baseUrl: format === 'anthropic' ? 'https://api.anthropic.com' : 'https://api.openai.com/v1',
    model: format === 'anthropic' ? 'claude-3-5-sonnet-latest' : 'gpt-4o-mini',
    apiKey: '',
    temperature: 0.2,
    maxTokens: 1024,
  }
}

export function emptyAiSettings(): AiSettings {
  return { schemaVersion: AI_SCHEMA_VERSION, updatedAt: new Date().toISOString(), tasks: {} }
}

export function taskSupportsFormat(task: AiTask, format: AiFormat): boolean {
  return !(format === 'anthropic' && OPENAI_ONLY_TASKS.includes(task))
}

export function maskApiKey(apiKey: string): string {
  if (!apiKey) return '未填写'
  if (apiKey.length <= 8) return `${apiKey.slice(0, 2)}****`
  return `${apiKey.slice(0, 4)}****${apiKey.slice(-4)}`
}

/** Wire payload the backend expects (snake_case, snake_case keys). */
export function toWireConfig(config: AiConfig): Record<string, unknown> {
  return {
    format: config.format,
    base_url: config.baseUrl.trim().replace(/\/+$/, ''),
    model: config.model.trim(),
    api_key: config.apiKey.trim(),
    temperature: config.temperature,
    max_tokens: config.maxTokens,
  }
}

function base64UrlEncode(text: string): string {
  const bytes = new TextEncoder().encode(text)
  let binary = ''
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte)
  })
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/** `X-AI-Config: base64url(JSON)` — see plan §5.3. */
export function encodeAiConfigHeader(config: AiConfig): string {
  return base64UrlEncode(JSON.stringify(toWireConfig(config)))
}

export function isValidAiConfig(config: Partial<AiConfig> | null | undefined): boolean {
  if (!config) return false
  return Boolean(config.baseUrl?.trim() && config.model?.trim() && config.apiKey?.trim())
}

export interface AiTestResult {
  ok: boolean
  format: AiFormat
  model: string | null
  latency_ms: number | null
  reply: string | null
  error: string | null
  hint: string | null
}

export interface AiMetrics {
  calls: number
  failures: number
  average_latency_ms: number
  by_format: Record<string, number>
}
