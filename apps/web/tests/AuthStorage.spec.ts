import { beforeEach, describe, expect, it } from 'vitest'

import { clearAccessToken, demoAuthEnabled, getAccessToken, setAccessToken } from '@/auth-storage'

describe('auth storage', () => {
  beforeEach(() => sessionStorage.clear())

  it('只在当前浏览器会话保存并可清除 token', () => {
    expect(getAccessToken()).toBeNull()
    setAccessToken('signed-token')
    expect(getAccessToken()).toBe('signed-token')
    clearAccessToken()
    expect(getAccessToken()).toBeNull()
  })

  it('本地开发未显式关闭时保留演示模式', () => {
    expect(demoAuthEnabled()).toBe(true)
  })
})
