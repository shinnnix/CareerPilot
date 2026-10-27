const $ = (id) => document.getElementById(id)
const PROFILE_KEY = 'profile'
const SUPPORTED_SCHEMA = 1
let fields = []

async function load() {
  const saved = await chrome.storage.local.get([
    'apiBase',
    'token',
    'applicationId',
    'resumeId',
    PROFILE_KEY,
  ])
  for (const key of ['apiBase', 'token', 'applicationId', 'resumeId']) {
    if (saved[key]) $(key).value = saved[key]
  }
  renderProfileStatus(saved[PROFILE_KEY])
}

function renderProfileStatus(profile) {
  if (!profile?.fields) {
    $('profileStatus').textContent = '未导入'
    return
  }
  const basic = profile.fields.basic ?? {}
  const who = [basic.name, basic.phone, basic.email].filter(Boolean).join(' · ')
  $('profileStatus').textContent = `已导入 v${profile.profileVersion} · ${who || '无基本信息'}`
}

async function save() {
  await chrome.storage.local.set({
    apiBase: $('apiBase').value.trim().replace(/\/$/, ''),
    token: $('token').value.trim(),
    applicationId: $('applicationId').value.trim(),
    resumeId: $('resumeId').value.trim(),
  })
}

async function readProfile() {
  const stored = await chrome.storage.local.get(PROFILE_KEY)
  return stored?.[PROFILE_KEY] ?? null
}

$('saveProfile').addEventListener('click', async () => {
  const raw = $('profileJson').value.trim()
  if (!raw) {
    $('status').textContent = '先粘贴导出的 JSON。'
    return
  }
  let parsed
  try {
    parsed = JSON.parse(raw)
  } catch {
    $('status').textContent = '不是合法的 JSON 文本。'
    return
  }
  const schemaVersion = Number(parsed?.schemaVersion ?? SUPPORTED_SCHEMA)
  if (!Number.isFinite(schemaVersion) || schemaVersion > SUPPORTED_SCHEMA) {
    $('status').textContent = `不支持的 schemaVersion：${parsed?.schemaVersion}`
    return
  }
  // Exported files keep the fields at the top level; synced payloads nest them.
  const fieldsPart = parsed.fields && typeof parsed.fields === 'object' ? parsed.fields : parsed
  const profile = {
    schemaVersion,
    profileVersion: Math.max(1, Number(parsed.profileVersion ?? 1) || 1),
    updatedAt: typeof parsed.updatedAt === 'string' ? parsed.updatedAt : new Date().toISOString(),
    source: 'manual',
    fields: fieldsPart,
  }
  await chrome.storage.local.set({ [PROFILE_KEY]: profile })
  $('profileJson').value = ''
  renderProfileStatus(profile)
  $('status').textContent = '已保存粘贴的个人信息。'
})

$('clearProfile').addEventListener('click', async () => {
  await chrome.storage.local.remove(PROFILE_KEY)
  renderProfileStatus(null)
  $('status').textContent = '已清除本地个人信息。'
})

$('scan').addEventListener('click', async () => {
  await save()
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  const result = await chrome.tabs.sendMessage(tab.id, { type: 'scan' })
  fields = result.fields
  $('fill').disabled = fields.length === 0
  $('status').textContent = `识别到 ${fields.length} 个可见字段。`
})

$('fill').addEventListener('click', async () => {
  await save()
  if (!$('token').value || !$('applicationId').value || !$('resumeId').value) {
    $('status').textContent = '请先填写 Token、投递记录 ID 和简历文档 ID。'
    return
  }
  $('status').textContent = '正在生成带来源的填写计划……'
  const profile = await readProfile()
  const body = { resume_document_id: $('resumeId').value, fields }
  // Plan §5.1: the profile is used for this mapping run only and never stored.
  if (profile?.fields) body.profile = profile.fields
  const response = await fetch(
    `${$('apiBase').value.replace(/\/$/, '')}/applications/${encodeURIComponent($('applicationId').value)}/autofill-plan`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${$('token').value}` },
      body: JSON.stringify(body),
    },
  )
  const plan = await response.json()
  if (!response.ok) {
    $('status').textContent = plan.message || '生成计划失败。'
    return
  }
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  await chrome.tabs.sendMessage(tab.id, {
    type: 'fill',
    fields: plan.fields.filter((item) => item.status === 'ready'),
  })
  $('status').textContent = `已填写 ${plan.ready_count} 个字段；${plan.review_count} 个字段需要人工审核。\nRun: ${plan.run_id}`
})

load()
