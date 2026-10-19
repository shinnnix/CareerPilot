import axios from 'axios'

import { clearAccessToken, demoAuthEnabled, getAccessToken } from '@/auth-storage'

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
  return config
})

apiClient.interceptors.response.use(undefined, (error) => {
  if (error.response?.status === 401 && !demoAuthEnabled()) {
    clearAccessToken()
    if (window.location.pathname !== '/login') window.location.assign('/login')
  }
  return Promise.reject(error)
})
