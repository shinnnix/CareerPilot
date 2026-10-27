/**
 * CareerPilot Autofill — service worker (plan §5.1.4, channel ①).
 *
 * The CareerPilot web app pushes the browser-local profile here with
 * `chrome.runtime.sendMessage(extensionId, {...})`. Nothing leaves the machine.
 */

const PROFILE_KEY = 'profile'
const SUPPORTED_SCHEMA = 1

function normalise(message) {
  const schemaVersion = Number(message?.schemaVersion ?? SUPPORTED_SCHEMA)
  if (!Number.isFinite(schemaVersion) || schemaVersion > SUPPORTED_SCHEMA) {
    return { ok: false, error: `不支持的 schemaVersion：${message?.schemaVersion}` }
  }
  if (!message?.fields || typeof message.fields !== 'object') {
    return { ok: false, error: '缺少 fields' }
  }
  return {
    ok: true,
    profile: {
      schemaVersion,
      profileVersion: Math.max(1, Number(message.profileVersion ?? 1) || 1),
      updatedAt: typeof message.updatedAt === 'string' ? message.updatedAt : new Date().toISOString(),
      source: 'page',
      fields: message.fields,
    },
  }
}

async function saveProfile(message) {
  const result = normalise(message)
  if (!result.ok) return result
  const stored = await chrome.storage.local.get(PROFILE_KEY)
  const existing = stored?.[PROFILE_KEY]
  // Newer wins: a stale page tab must not overwrite a fresher profile.
  if (existing && Number(existing.profileVersion) > result.profile.profileVersion) {
    return { ok: true, profileVersion: existing.profileVersion, skipped: 'stale' }
  }
  await chrome.storage.local.set({ [PROFILE_KEY]: result.profile })
  return { ok: true, profileVersion: result.profile.profileVersion }
}

chrome.runtime.onMessageExternal.addListener((message, _sender, sendResponse) => {
  if (message?.type === 'CAREERPILOT_PING') {
    sendResponse({ ok: true, version: chrome.runtime.getManifest().version })
    return true
  }
  if (message?.type === 'CAREERPILOT_PROFILE_SYNC') {
    saveProfile(message)
      .then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: String(error?.message ?? error) }))
    return true
  }
  sendResponse({ ok: false, error: `未知消息类型：${message?.type}` })
  return true
})
