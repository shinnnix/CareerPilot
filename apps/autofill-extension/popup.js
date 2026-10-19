const $ = (id) => document.getElementById(id)
let fields = []

async function load() {
  const saved = await chrome.storage.local.get(['apiBase', 'token', 'applicationId', 'resumeId'])
  for (const key of ['apiBase', 'token', 'applicationId', 'resumeId']) {
    if (saved[key]) $(key).value = saved[key]
  }
}

async function save() {
  await chrome.storage.local.set({
    apiBase: $('apiBase').value.trim().replace(/\/$/, ''),
    token: $('token').value.trim(),
    applicationId: $('applicationId').value.trim(),
    resumeId: $('resumeId').value.trim(),
  })
}

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
    $('status').textContent = '请先填写 Token、申请记录 ID 和简历文档 ID。'
    return
  }
  $('status').textContent = '正在生成带来源的填写计划……'
  const response = await fetch(`${$('apiBase').value.replace(/\/$/, '')}/applications/${encodeURIComponent($('applicationId').value)}/autofill-plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${$('token').value}` },
    body: JSON.stringify({ resume_document_id: $('resumeId').value, fields }),
  })
  const plan = await response.json()
  if (!response.ok) {
    $('status').textContent = plan.message || '生成计划失败。'
    return
  }
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  await chrome.tabs.sendMessage(tab.id, { type: 'fill', fields: plan.fields.filter((item) => item.status === 'ready') })
  $('status').textContent = `已填写 ${plan.ready_count} 个字段；${plan.review_count} 个字段需要人工审核。\nRun: ${plan.run_id}`
})

load()
