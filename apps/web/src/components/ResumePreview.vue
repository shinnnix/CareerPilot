<script setup lang="ts">
import { computed } from 'vue'

import type { ResumeHead, ResumeSection, ResumeTemplate } from '@/types/resumes'

const props = withDefaults(
  defineProps<{
    head: ResumeHead
    sections: ResumeSection[]
    template?: ResumeTemplate
    fontSize?: number
    activeSectionId?: string | null
    showEmpty?: boolean
    interactive?: boolean
    caption?: string
  }>(),
  {
    template: 'classic',
    fontSize: 14,
    activeSectionId: null,
    showEmpty: true,
    interactive: false,
    caption: '',
  },
)

const emit = defineEmits<{ (event: 'select', sectionId: string): void }>()

const visibleSections = computed(() =>
  props.showEmpty ? props.sections : props.sections.filter((section) => section.entries.length > 0),
)

const contactItems = computed(() => {
  const items: string[] = []
  if (props.head.phone) items.push(props.head.phone)
  if (props.head.email) items.push(props.head.email)
  if (props.head.city) items.push(props.head.city)
  props.head.links.forEach((link) => items.push(link.url))
  return items
})

function isParagraphSection(section: ResumeSection): boolean {
  return section.key === 'summary' || section.key === 'other'
}

function select(section: ResumeSection) {
  if (props.interactive) emit('select', section.id)
}
</script>

<template>
  <article
    class="resume-paper"
    :class="[`resume-paper--${template}`, { 'resume-paper--interactive': interactive }]"
    :data-template="template"
    :style="{ fontSize: `${fontSize}px` }"
  >
    <p v-if="caption" class="resume-paper-caption">{{ caption }}</p>
    <header class="resume-head">
      <h1>{{ head.name || '未填写姓名' }}</h1>
      <p v-if="head.target_title" class="resume-target">{{ head.target_title }}</p>
      <p v-if="contactItems.length" class="resume-contact">
        <span v-for="item in contactItems" :key="item">{{ item }}</span>
      </p>
    </header>

    <section
      v-for="section in visibleSections"
      :id="`resume-section-${section.id}`"
      :key="section.id"
      class="resume-section"
      :class="{
        'resume-section--active': section.id === activeSectionId,
        'resume-section--paragraph': isParagraphSection(section),
      }"
      :data-section-key="section.key"
      @click="select(section)"
    >
      <h2>{{ section.title }}</h2>
      <div v-for="entry in section.entries" :key="entry.id" class="resume-entry">
        <div v-if="entry.title || entry.period" class="resume-entry-head">
          <strong v-if="entry.title && !isParagraphSection(section)">{{ entry.title }}</strong>
          <p v-if="entry.title && isParagraphSection(section)" class="resume-paragraph">
            {{ entry.title }}
          </p>
          <span v-if="entry.period" class="resume-entry-period">{{ entry.period }}</span>
        </div>
        <p v-if="entry.subtitle" class="resume-entry-subtitle">{{ entry.subtitle }}</p>
        <ul v-if="entry.bullets.length" class="resume-bullets">
          <li v-for="(bullet, bulletIndex) in entry.bullets" :key="bulletIndex">{{ bullet }}</li>
        </ul>
      </div>
      <p v-if="!section.entries.length" class="resume-section-empty">
        该章节尚未填写，可在右侧编辑或生成 AI 优化建议
      </p>
    </section>
  </article>
</template>
