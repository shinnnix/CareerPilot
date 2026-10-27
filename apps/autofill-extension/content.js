// Presence marker: the CareerPilot page uses it to offer sync channel ②
// (read the slim snapshot from localStorage) when direct messaging is unavailable.
document.documentElement.dataset.careerpilotExt = '1'

function labelFor(element) {
  if (element.labels?.length) return element.labels[0].innerText.trim()
  const labelled = element.getAttribute('aria-label') || element.getAttribute('placeholder')
  if (labelled) return labelled.trim()
  const parent = element.closest('label, fieldset, .form-group, .field, [class*="field"]')
  return parent?.innerText?.split('\n')[0]?.trim() || element.name || element.id || '未命名字段'
}

function fieldType(element) {
  if (element.tagName === 'SELECT') return 'select'
  if (element.tagName === 'TEXTAREA') return 'textarea'
  if (element.type === 'file') return 'file'
  if (element.type === 'email' || element.type === 'tel' || element.type === 'url') return element.type
  if (element.type === 'checkbox') return 'checkbox'
  return 'text'
}

function scan() {
  const elements = [...document.querySelectorAll('input, textarea, select')]
    .filter((element) => !element.disabled && element.type !== 'hidden' && element.offsetParent !== null)
  return elements.map((element, index) => ({
    field_id: element.id || element.name || `field-${index}`,
    label: labelFor(element),
    field_type: fieldType(element),
    required: element.required,
    options: element.tagName === 'SELECT' ? [...element.options].map((option) => option.textContent.trim()) : [],
  }))
}

function setValue(element, value) {
  const setter = Object.getOwnPropertyDescriptor(element.constructor.prototype, 'value')?.set
  if (setter) setter.call(element, value)
  else element.value = value
  element.dispatchEvent(new Event('input', { bubbles: true }))
  element.dispatchEvent(new Event('change', { bubbles: true }))
}

function fill(fields) {
  const elements = [...document.querySelectorAll('input, textarea, select')]
  let filled = 0
  for (const plan of fields) {
    const element = elements.find((candidate, index) => (candidate.id || candidate.name || `field-${index}`) === plan.field_id)
    if (!element || plan.value == null) continue
    if (element.tagName === 'SELECT') {
      const option = [...element.options].find((candidate) => candidate.value === plan.value || candidate.textContent.trim() === plan.value)
      if (!option) continue
      setValue(element, option.value)
    } else if (element.type !== 'file' && element.type !== 'checkbox') {
      setValue(element, plan.value)
    }
    filled += 1
  }
  return filled
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === 'scan') sendResponse({ fields: scan() })
  if (message.type === 'fill') sendResponse({ filled: fill(message.fields) })
  return true
})
