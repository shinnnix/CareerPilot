<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  Check,
  Delete,
  Download,
  Edit,
  MagicStick,
  Plus,
  Refresh,
  Sort,
} from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'

import { getApiErrorMessage } from '@/api/errors'
import { listJobCatalog } from '@/api/workspace'
import { listDocuments } from '@/api/documents'
import {
  deleteResume,
  exportResume,
  getResume,
  reparseResume,
  updateResume,
} from '@/api/resumes'
import ResumeOptimizationPanel from '@/components/ResumeOptimizationPanel.vue'
import ResumePreview from '@/components/ResumePreview.vue'
import ResumeTemplatePicker from '@/components/ResumeTemplatePicker.vue'
import type { DocumentSummary } from '@/types/documents'
import type {
  ResumeDetail,
  ResumeEntry,
  ResumeHead,
  ResumeSection,
  ResumeTemplate,
  ResumeUpdateInput,
} from '@/types/resumes'
import type { JobRow } from '@/types/workspace'

const route = useRoute()
const router = useRouter()
const resumeId = computed(() => String(route.params.id))

const resume = ref<ResumeDetail | null>(null)
const announcements = ref<JobRow[]>([])
const jdDocuments = ref<DocumentSummary[]>([])
const loading = ref(true)
const saving = ref(false)
const errorMessage = ref('')
const dirty = ref(false)
const activeSectionId = ref<string | null>(null)
const optimizeOpen = ref(false)
const focusHint = ref('')
const presetAnnouncementId = ref('')
let queryApplied = false

function emptyHead(): ResumeHead {
  return { name: null, target_title: null, phone: null, email: null, city: null, links: [] }
}

const titleDraft = ref('')
const template = ref<ResumeTemplate>('classic')
const fontSize = ref(14)
const draftHead = ref<ResumeHead>(emptyHead())
const draftSections = ref<ResumeSection[]>([])

const editOpen = ref(false)
const editMode = ref<'head' | 'section' | null>(null)
const editingHead = ref<ResumeHead | null>(null)
const editingSection = ref<ResumeSection | null>(null)
const bulletTexts = ref<Record<string, string>>({})
const sortOpen = ref(false)

const templateLabels: Record<ResumeTemplate, string> = {
  classic: '经典简约',
  modern: '现代商务',
  elegant: '雅致居中',
  compact: '紧凑黑白',
}

const activeSection = computed(
  () => draftSections.value.find((section) => section.id === activeSectionId.value) || null,
)
const analysisWarnings = computed(() => resume.value?.analysis.warnings || [])
const sectionEntryCount = computed(() =>
  draftSections.value.reduce((total, section) => total + section.entries.length, 0),
)

function deepCopy<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function makeId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`
}

function formatTime(value: string | undefined): string {
  return value ? new Date(value).toLocaleString() : '—'
}

function applyServer(detail: ResumeDetail) {
  resume.value = detail
  draftHead.value = deepCopy(detail.head)
  draftSections.value = deepCopy(detail.sections)
  titleDraft.value = detail.title
  template.value = detail.template
  fontSize.value = detail.font_size
  dirty.value = false
  if (!activeSectionId.value || !detail.sections.some((item) => item.id === activeSectionId.value)) {
    activeSectionId.value = detail.sections[0]?.id || null
  }
}
async function loadAll() {
  loading.value = true
  errorMessage.value = ''
  try {
    const [detail, catalogResult, jdResult] = await Promise.all([
      getResume(resumeId.value),
      listJobCatalog({ page_size: 100 }),
      listDocuments({ document_type: 'job_description', page_size: 100 }),
    ])
    announcements.value = catalogResult.items
    jdDocuments.value = jdResult.items
    applyServer(detail)
    await applyRouteQuery(detail)
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  } finally {
    loading.value = false
  }
}

/**
 * Entry contract from 公告详情 / 投递准备页:
 * `/workspace/resumes/:id?announcement=<announcementId>&optimize=1`
 * Applied once on first load only, so later edits are never overwritten.
 */
async function applyRouteQuery(detail: ResumeDetail) {
  if (queryApplied) return
  queryApplied = true
  const announcementParam =
    typeof route.query.announcement === 'string' ? route.query.announcement : ''
  const shouldOptimize = route.query.optimize === '1'
  if (!announcementParam && !shouldOptimize) return

  if (
    announcementParam &&
    announcementParam !== detail.target_announcement_id &&
    announcements.value.some((row) => row.id === announcementParam)
  ) {
    presetAnnouncementId.value = announcementParam
    try {
      resume.value = await updateResume(detail.id, {
        target_announcement_id: announcementParam,
      })
      ElMessage.success('已按该公告设置目标岗位')
    } catch (error) {
      ElMessage.error(getApiErrorMessage(error))
    }
  } else if (announcementParam) {
    presetAnnouncementId.value = announcementParam
  }
  if (shouldOptimize) optimizeOpen.value = true
  await router.replace({ path: route.path })
}

async function persistSettings(changes: ResumeUpdateInput) {
  if (!resume.value) return
  try {
    const updated = await updateResume(resume.value.id, changes)
    resume.value = updated
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
    if (resume.value) {
      template.value = resume.value.template
      fontSize.value = resume.value.font_size
    }
  }
}

function changeTemplate(value: ResumeTemplate) {
  template.value = value
  if (!resume.value || value === resume.value.template) return
  void persistSettings({ template: value })
}

function changeFontSize(delta: number) {
  const next = Math.min(22, Math.max(10, fontSize.value + delta))
  if (next === fontSize.value) return
  fontSize.value = next
  void persistSettings({ font_size: next })
}

async function save() {
  if (!resume.value) return
  saving.value = true
  try {
    const updated = await updateResume(resume.value.id, {
      title: titleDraft.value.trim() || resume.value.title,
      template: template.value,
      font_size: fontSize.value,
      head: draftHead.value,
      sections: draftSections.value,
      target_announcement_id: resume.value.target_announcement_id,
    })
    applyServer(updated)
    ElMessage.success(`已保存为 v${updated.content_version}`)
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    saving.value = false
  }
}

function openOptimize() {
  if (dirty.value) {
    ElMessage.warning('请先保存当前编辑，再生成 AI 优化建议')
    return
  }
  optimizeOpen.value = true
}

async function changeTargetAnnouncement(value: unknown) {
  if (!resume.value) return
  const announcementId = typeof value === 'string' && value ? value : null
  try {
    const updated = await updateResume(resume.value.id, {
      target_announcement_id: announcementId,
    })
    resume.value = updated
    ElMessage.success(announcementId ? '已设置目标岗位公告' : '已清除目标岗位')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

function handleApplied(updated: ResumeDetail) {
  applyServer(updated)
  ElMessage.success('简历已应用新的优化版本')
}

function handleReverted(updated: ResumeDetail) {
  applyServer(updated)
  ElMessage.success('已撤销应用，简历恢复到应用前版本')
}

function focusSection(sectionId: string) {
  activeSectionId.value = sectionId
  document
    .getElementById(`resume-section-${sectionId}`)
    ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function openHeadEditor() {
  if (!draftHead.value) return
  editingHead.value = deepCopy(draftHead.value)
  editMode.value = 'head'
  editOpen.value = true
}

function openSectionEditor(sectionId: string) {
  const section = draftSections.value.find((item) => item.id === sectionId)
  if (!section) return
  activeSectionId.value = sectionId
  editingSection.value = deepCopy(section)
  bulletTexts.value = Object.fromEntries(
    editingSection.value.entries.map((entry) => [entry.id, entry.bullets.join('\n')]),
  )
  editMode.value = 'section'
  editOpen.value = true
}

function addEntry() {
  if (!editingSection.value) return
  const entry: ResumeEntry = {
    id: makeId(editingSection.value.id),
    title: '',
    subtitle: null,
    period: null,
    bullets: [],
  }
  editingSection.value.entries.push(entry)
  bulletTexts.value = { ...bulletTexts.value, [entry.id]: '' }
}

function removeEntry(entryId: string) {
  if (!editingSection.value) return
  editingSection.value.entries = editingSection.value.entries.filter(
    (entry) => entry.id !== entryId,
  )
  const next = { ...bulletTexts.value }
  delete next[entryId]
  bulletTexts.value = next
}

function confirmEdit() {
  if (editMode.value === 'head' && editingHead.value) {
    draftHead.value = deepCopy(editingHead.value)
    dirty.value = true
  } else if (editMode.value === 'section' && editingSection.value) {
    const section = editingSection.value
    section.entries = section.entries.map((entry) => ({
      ...entry,
      bullets: (bulletTexts.value[entry.id] || '')
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean),
    }))
    const index = draftSections.value.findIndex((item) => item.id === section.id)
    if (index >= 0) draftSections.value[index] = section
    dirty.value = true
  }
  editOpen.value = false
}

function moveSection(index: number, direction: -1 | 1) {
  const target = index + direction
  if (target < 0 || target >= draftSections.value.length) return
  const [item] = draftSections.value.splice(index, 1)
  draftSections.value.splice(target, 0, item)
  dirty.value = true
}

function updateLinks(raw: string) {
  if (!editingHead.value) return
  editingHead.value.links = raw
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [label, url] = line.split('|').map((part) => part.trim())
      return { label: label || '链接', url: url || label }
    })
}

async function handleExport(command: unknown) {
  await download(command === 'html' ? 'html' : 'markdown')
}

async function download(format: 'markdown' | 'html') {
  if (!resume.value) return
  try {
    const content = await exportResume(resume.value.id, format)
    const mime = format === 'html' ? 'text/html;charset=utf-8' : 'text/markdown;charset=utf-8'
    const url = URL.createObjectURL(new Blob([content], { type: mime }))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${draftHead.value?.name || resume.value.title}.${
      format === 'html' ? 'html' : 'md'
    }`
    anchor.click()
    URL.revokeObjectURL(url)
    ElMessage.success(`已导出 ${format === 'html' ? 'HTML' : 'Markdown'}`)
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

async function handleReparse() {
  const confirmed = await ElMessageBox.confirm(
    '将按当前解析器从原文重建章节结构，人工编辑会被覆盖，确认继续吗？',
    '重新解析简历',
    { type: 'warning', confirmButtonText: '重新解析', cancelButtonText: '取消' },
  )
    .then(() => true)
    .catch(() => false)
  if (!confirmed || !resume.value) return
  try {
    const updated = await reparseResume(resume.value.id)
    applyServer(updated)
    ElMessage.success('已重新解析，请检查章节内容')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

async function handleDelete() {
  if (!resume.value) return
  const confirmed = await ElMessageBox.confirm(
    '将删除简历工作台和全部优化记录，知识库原文会保留，确认继续吗？',
    '删除简历',
    { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' },
  )
    .then(() => true)
    .catch(() => false)
  if (!confirmed) return
  try {
    await deleteResume(resume.value.id)
    ElMessage.success('简历已删除')
    await router.push('/workspace/resumes')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

onMounted(loadAll)
</script>

<template>
  <main class="page resume-page">
    <el-skeleton v-if="loading" :rows="14" animated class="surface" />
    <el-result
      v-else-if="errorMessage"
      icon="error"
      title="无法加载简历"
      :sub-title="errorMessage"
    >
      <template #extra>
        <el-button @click="loadAll">重新加载</el-button>
      </template>
    </el-result>

    <template v-else-if="resume">
      <div class="resume-topbar">
        <RouterLink class="back-link" to="/workspace/resumes">
          <el-icon><ArrowLeft /></el-icon>
          简历列表
        </RouterLink>
        <div class="resume-topbar-main">
          <el-input
            v-model="titleDraft"
            class="resume-title-input"
            maxlength="200"
            @input="dirty = true"
          />
          <p class="muted-note">
            v{{ resume.content_version }} · {{ templateLabels[template] }} ·
            {{ fontSize }}px · 更新于 {{ formatTime(resume.updated_at) }}
          </p>
        </div>
        <div class="resume-toolbar">
          <div class="font-size-control">
            <span>字号</span>
            <el-button size="small" circle :disabled="fontSize <= 10" @click="changeFontSize(-1)">
              −
            </el-button>
            <strong>{{ fontSize }}px</strong>
            <el-button size="small" circle :disabled="fontSize >= 22" @click="changeFontSize(1)">
              +
            </el-button>
          </div>
          <el-button :icon="Sort" @click="sortOpen = true">模块排序</el-button>
          <el-button :icon="Refresh" @click="handleReparse">重新解析</el-button>
          <el-button type="primary" :icon="MagicStick" @click="openOptimize">AI 优化</el-button>
          <el-button :icon="Check" :loading="saving" :disabled="!dirty" @click="save">
            保存
          </el-button>
          <el-dropdown trigger="click" @command="handleExport">
            <el-button :icon="Download">导出</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="markdown">导出 Markdown</el-dropdown-item>
                <el-dropdown-item command="html">导出 HTML</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>

      <div class="resume-layout">
        <aside class="resume-side">
          <section class="surface">
            <div class="section-heading section-heading--compact">
              <div>
                <p class="eyebrow">TEMPLATE</p>
                <h2>简历模板</h2>
              </div>
            </div>
            <p class="panel-note">切换后实时预览，模板随简历保存并用于导出。</p>
            <ResumeTemplatePicker :model-value="template" @update:model-value="changeTemplate" />
          </section>

          <section class="surface resume-nav">
            <div class="section-heading section-heading--compact">
              <div>
                <p class="eyebrow">SECTIONS</p>
                <h2>章节</h2>
              </div>
              <span>{{ sectionEntryCount }} 条目</span>
            </div>
            <ul>
              <li>
                <button type="button" class="resume-nav-item" @click="openHeadEditor">
                  基本信息
                  <span>{{ draftHead.name || '未填写' }}</span>
                </button>
              </li>
              <li v-for="section in draftSections" :key="section.id">
                <button
                  type="button"
                  class="resume-nav-item"
                  :class="{ 'resume-nav-item--active': section.id === activeSectionId }"
                  @click="focusSection(section.id)"
                >
                  {{ section.title }}
                  <span>{{ section.entries.length }}</span>
                </button>
              </li>
            </ul>
            <div class="resume-nav-actions">
              <el-button
                size="small"
                :icon="Edit"
                :disabled="!activeSection"
                @click="activeSection && openSectionEditor(activeSection.id)"
              >
                编辑「{{ activeSection?.title || '章节' }}」
              </el-button>
            </div>
          </section>

          <section class="surface">
            <div class="section-heading section-heading--compact">
              <div>
                <p class="eyebrow">TARGET</p>
                <h2>目标岗位</h2>
              </div>
            </div>
            <el-select
              :model-value="resume.target_announcement_id || ''"
              class="full-width"
              clearable
              filterable
              placeholder="未设置，可随时选择公告"
              @update:model-value="changeTargetAnnouncement"
            >
              <el-option
                v-for="announcement in announcements"
                :key="announcement.id"
                :label="`${announcement.company.name} · ${announcement.title}`"
                :value="announcement.id"
              />
            </el-select>
            <p class="panel-note optimize-target-note">
              AI 优化默认按这里的职位公告生成匹配报告；也可以在优化面板临时切换 JD。
            </p>
          </section>

          <section v-if="analysisWarnings.length" class="surface resume-analysis">
            <p class="eyebrow">PARSER</p>
            <h2>解析提示</h2>
            <p class="muted-note">
              解析置信度 {{ Math.round(resume.analysis.confidence * 100) }}% ·
              {{ resume.analysis.parser_version }}
            </p>
            <ul class="resume-analysis-list">
              <li v-for="warning in analysisWarnings" :key="warning">{{ warning }}</li>
            </ul>
            <RouterLink
              v-if="resume.document_id"
              class="source-link"
              :to="`/workspace/library/${resume.document_id}`"
            >
              查看知识库原文与 Chunk →
            </RouterLink>
          </section>
        </aside>

        <section class="resume-main">
          <div class="resume-focus-row">
            <el-input
              v-model="focusHint"
              placeholder="告诉 AI 这次优化的重点（可选），例如：突出 RAG 与评测经验"
              maxlength="300"
              clearable
            />
            <el-button type="primary" :icon="MagicStick" @click="openOptimize">AI 优化</el-button>
          </div>

          <ResumePreview
            :head="draftHead"
            :sections="draftSections"
            :template="template"
            :font-size="fontSize"
            :active-section-id="activeSectionId"
            interactive
            @select="activeSectionId = $event"
          />

          <div class="resume-footer">
            <span class="muted-note">
              {{ dirty ? '有未保存的修改' : '所有修改已保存' }} ·
              点击任意章节可在左侧编辑
            </span>
            <div class="resume-footer-actions">
              <el-button :icon="Delete" type="danger" plain @click="handleDelete">删除简历</el-button>
              <el-button :icon="Check" type="primary" :loading="saving" :disabled="!dirty" @click="save">
                保存修改
              </el-button>
            </div>
          </div>
        </section>
      </div>
    </template>

    <el-drawer
      v-if="resume"
      v-model="optimizeOpen"
      title="AI 简历优化"
      size="780px"
      :destroy-on-close="false"
    >
      <ResumeOptimizationPanel
        :resume="resume"
        :announcements="announcements"
        :jd-documents="jdDocuments"
        :focus-hint="focusHint"
        :preset-announcement-id="presetAnnouncementId"
        @applied="handleApplied"
        @reverted="handleReverted"
      />
    </el-drawer>

    <el-dialog
      v-model="editOpen"
      :title="editMode === 'head' ? '编辑基本信息' : `编辑「${editingSection?.title || ''}」`"
      width="720px"
    >
      <el-form v-if="editMode === 'head' && editingHead" label-position="top">
        <div class="form-grid">
          <el-form-item label="姓名">
            <el-input v-model="editingHead.name" clearable />
          </el-form-item>
          <el-form-item label="求职意向">
            <el-input v-model="editingHead.target_title" clearable />
          </el-form-item>
          <el-form-item label="电话">
            <el-input v-model="editingHead.phone" clearable />
          </el-form-item>
          <el-form-item label="邮箱">
            <el-input v-model="editingHead.email" clearable />
          </el-form-item>
          <el-form-item label="城市">
            <el-input v-model="editingHead.city" clearable />
          </el-form-item>
        </div>
        <el-form-item label="主页 / 作品链接（每行一个，格式：标签 | 链接）">
          <el-input
            :model-value="editingHead.links.map((link) => `${link.label} | ${link.url}`).join('\n')"
            type="textarea"
            :rows="3"
            placeholder="GitHub | https://github.com/your-name"
            @update:model-value="updateLinks(String($event))"
          />
        </el-form-item>
      </el-form>

      <el-form v-else-if="editMode === 'section' && editingSection" label-position="top">
        <el-form-item label="章节标题">
          <el-input v-model="editingSection.title" maxlength="50" />
        </el-form-item>
        <div
          v-for="(entry, index) in editingSection.entries"
          :key="entry.id"
          class="entry-editor"
        >
          <div class="entry-editor-head">
            <strong>条目 {{ index + 1 }}</strong>
            <el-button size="small" type="danger" link @click="removeEntry(entry.id)">删除条目</el-button>
          </div>
          <div class="form-grid">
            <el-form-item label="标题">
              <el-input v-model="entry.title" maxlength="300" />
            </el-form-item>
            <el-form-item label="副标题 / 技术栈">
              <el-input v-model="entry.subtitle" maxlength="300" />
            </el-form-item>
            <el-form-item label="时间">
              <el-input v-model="entry.period" maxlength="100" placeholder="2024.09-2027.06" />
            </el-form-item>
          </div>
          <el-form-item label="描述（每行一条要点）">
            <el-input
              v-model="bulletTexts[entry.id]"
              type="textarea"
              :rows="4"
              placeholder="每行一个要点，保存时自动拆分"
            />
          </el-form-item>
        </div>
        <el-button :icon="Plus" @click="addEntry">添加条目</el-button>
      </el-form>

      <template #footer>
        <el-button @click="editOpen = false">取消</el-button>
        <el-button type="primary" @click="confirmEdit">确认修改</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="sortOpen" title="模块排序" width="520px">
      <p class="panel-note">导出和预览都按这里的顺序渲染，基本信息固定在顶部。</p>
      <ul class="sort-list">
        <li v-for="(section, index) in draftSections" :key="section.id" class="sort-row">
          <span>{{ index + 1 }}. {{ section.title }}</span>
          <span class="sort-actions">
            <el-button size="small" :disabled="index === 0" @click="moveSection(index, -1)">
              上移
            </el-button>
            <el-button
              size="small"
              :disabled="index === draftSections.length - 1"
              @click="moveSection(index, 1)"
            >
              下移
            </el-button>
          </span>
        </li>
      </ul>
      <template #footer>
        <el-button type="primary" @click="sortOpen = false">完成排序</el-button>
      </template>
    </el-dialog>
  </main>
</template>
