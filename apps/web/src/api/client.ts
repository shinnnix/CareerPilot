import axios from 'axios'

import { aiConfigHeader } from '@/ai-storage'
import { clearAccessToken, demoAuthEnabled, getAccessToken } from '@/auth-storage'
import { AI_CONFIG_HEADER } from '@/types/ai'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 10_000,
})

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  } else if (demoAuthEnabled()) {
    config.headers['X-User-ID'] = 'demo-user'
  }
  // Plan §5.3: credentials travel per request, in memory only. Callers that need
  // a specific task (e.g. extraction) set the header themselves and win.
  if (!config.headers[AI_CONFIG_HEADER]) {
    const header = aiConfigHeader('chat')
    if (header) config.headers[AI_CONFIG_HEADER] = header
  }
  return config
})

apiClient.interceptors.response.use(undefined, (error) => {
  if (error.response?.status === 401 && !demoAuthEnabled()) {
    clearAccessToken()
    if (window.location.pathname !== '/login') window.location.assign('/login')
  }
  return Promise.reject(error)
})
