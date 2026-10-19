import { apiClient } from './client'
import type { AgentEventItem, AgentRun, AgentRunInput } from '@/types/agent'

export async function createAgentRun(payload: AgentRunInput): Promise<AgentRun> {
  const response = await apiClient.post<AgentRun>('/agent/runs', payload)
  return response.data
}

export async function confirmAgentRun(
  runId: string,
  approved: boolean,
  idempotencyKey: string,
): Promise<AgentRun> {
  const response = await apiClient.post<AgentRun>(`/agent/runs/${runId}/confirm`, {
    approved,
    idempotency_key: idempotencyKey,
  })
  return response.data
}

export async function resumeAgentRun(runId: string): Promise<AgentRun> {
  const response = await apiClient.post<AgentRun>(`/agent/runs/${runId}/resume`)
  return response.data
}

export function subscribeAgentEvents(
  runId: string,
  onEvent: (event: AgentEventItem) => void,
): EventSource {
  const base = import.meta.env.VITE_API_BASE_URL || '/api/v1'
  const source = new EventSource(`${base}/agent/runs/${runId}/events`)
  const eventNames = [
    'run_started',
    'intent_routed',
    'tool_planned',
    'tool_started',
    'confirmation_required',
    'confirmation_rejected',
    'checkpoint_recovered',
    'run_completed',
    'run_failed',
    'stream_end',
  ]
  for (const eventName of eventNames) {
    source.addEventListener(eventName, (event) => {
      const message = event as MessageEvent<string>
      onEvent({
        id: message.lastEventId,
        event: eventName,
        data: JSON.parse(message.data) as Record<string, unknown>,
      })
      if (eventName === 'stream_end') source.close()
    })
  }
  return source
}
