import { apiClient } from './client'

export interface AuthUser {
  id: string
  email: string
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: AuthUser
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>('/auth/login', { email, password })
  return response.data
}

export async function register(email: string, password: string): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>('/auth/register', { email, password })
  return response.data
}
