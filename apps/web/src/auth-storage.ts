const TOKEN_KEY = 'careerpilot_access_token'

export function getAccessToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY)
}

export function setAccessToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token)
}

export function clearAccessToken(): void {
  sessionStorage.removeItem(TOKEN_KEY)
}

export function demoAuthEnabled(): boolean {
  return import.meta.env.VITE_ALLOW_DEMO_AUTH !== 'false'
}
