/** AI settings + assistant chat API (plan §5.3 / §5.6). */

import { apiClient } from '@/api/client'
import { AI_CONFIG_HEADER, encodeAiConfigHeader } from '@/types/ai'
import type { AiConfig, AiMetrics, AiTestResult } from '@/types/ai'

export async function testAiConnection(config: AiConfig): Promise<AiTestResult> {
  const { data } = await apiClient.post<AiTestResult>(
    '/workspace/settings/ai/test',
    {
      format: config.format,
      base_url: config.baseUrl.trim().replace(/\/+$/, ''),
      model: config.model.trim(),
      api_key: config.apiKey.trim(),
      temperature: config.temperature,
      max_tokens: config.maxTokens,
    },
    { timeout: 25_000 },
  )
  return data
}

export async function getAiMetrics(): Promise<AiMetrics> {
  const { data } = await apiClient.get<AiMetrics>('/workspace/settings/ai/metrics')
  return data
}

export async function resetAiMetrics(): Promise<void> {
  await apiClient.delete('/workspace/settings/ai/metrics')
}

export interface AiEchoResult {
  configured: boolean
  format?: string
  base_url?: string
  model?: string
  temperature?: number
  max_tokens?: number
}

export async function echoAiConfig(config: AiConfig): Promise<AiEchoResult> {
  const { data } = await apiClient.get<AiEchoResult>('/workspace/settings/ai/echo', {
    headers: { [AI_CONFIG_HEADER]: encodeAiConfigHeader(config) },
  })
  return data
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatReply {
  reply: string
  format: string
  model: string
  latency_ms: number
}

export async function sendAssistantMessage(
  message: string,
  history: ChatMessage[],
  config: AiConfig | null,
): Promise<ChatReply> {
  const headers: Record<string, string> = {}
  if (config) headers[AI_CONFIG_HEADER] = encodeAiConfigHeader(config)
  const { data } = await apiClient.post<ChatReply>(
    '/workspace/assistant/chat',
    { message, history: history.slice(-20) },
    { headers, timeout: 60_000 },
  )
  return data
}
