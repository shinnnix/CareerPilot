<script setup lang="ts">
import type { ResumeTemplate } from '@/types/resumes'

defineProps<{ modelValue: ResumeTemplate }>()
const emit = defineEmits<{ (event: 'update:modelValue', value: ResumeTemplate): void }>()

interface TemplateOption {
  value: ResumeTemplate
  label: string
  hint: string
  accent: string
}

const templates: TemplateOption[] = [
  { value: 'classic', label: '经典简约', hint: '偏色标记 · 清晰通用', accent: '#b2411f' },
  { value: 'modern', label: '现代商务', hint: '蓝色强调 · 利落专业', accent: '#2f6fb3' },
  { value: 'elegant', label: '雅致居中', hint: '居中抬头 · 沉稳留白', accent: '#1f6b58' },
  { value: 'compact', label: '紧凑黑白', hint: '紧凑排版 · 适合打印', accent: '#2b2b2b' },
]
</script>

<template>
  <div class="template-grid">
    <button
      v-for="template in templates"
      :key="template.value"
      type="button"
      class="template-card"
      :class="{ 'template-card--active': template.value === modelValue }"
      :aria-pressed="template.value === modelValue"
      :data-template="template.value"
      @click="emit('update:modelValue', template.value)"
    >
      <span class="template-thumb" :style="{ '--template-accent': template.accent }">
        <span class="template-thumb-title" />
        <span class="template-thumb-rule" />
        <span class="template-thumb-bars">
          <i />
          <i />
          <i />
        </span>
      </span>
      <span class="template-meta">
        <strong>{{ template.label }}</strong>
        <small>{{ template.hint }}</small>
      </span>
    </button>
  </div>
</template>
