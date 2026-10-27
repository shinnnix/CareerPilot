import axios from 'axios'

import type { ApiErrorPayload } from '@/types/jobs'

export function getApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiErrorPayload>(error)) {
    return error.response?.data?.message || '请求失败，请检查后端服务是否启动'
  }
  return error instanceof Error ? error.message : '发生未知错误'
}

export function getApiErrorCode(error: unknown): string | null {
  if (axios.isAxiosError<ApiErrorPayload>(error)) {
    return error.response?.data?.code || null
  }
  return null
}

export function getApiErrorDetails(error: unknown): Record<string, unknown> {
  if (axios.isAxiosError<ApiErrorPayload>(error)) {
    return error.response?.data?.details || {}
  }
  return {}
}
