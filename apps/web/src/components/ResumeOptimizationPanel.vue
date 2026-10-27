<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick, RefreshLeft } from '@element-plus/icons-vue'

import {
  applyResumeOptimization,
  discardResumeOptimization,
  getResumeOptimization,
  listResumeOptimizations,
  optimizeResume,
  revertResumeOptimization,
} from '@/api/resumes'
import { getApiErrorMessage } from '@/api/errors'
import MatchScoreBreakdown from '@/components/MatchScoreBreakdown.vue'
import ResumePreview from '@/components/ResumePreview.vue'
import type { DocumentSummary } from '@/types/documents'
import type {
  OptimizationStatus,
  ResumeDetail,
  ResumeOptimization,
  ResumeOptimizationSummary,
  ResumeOptimizeInput,
  ResumeSuggestion,
} from '@/types/resumes'
import type { JobRow } from '@/types/workspace'

const props = defineProps<{
  resume: ResumeDetail
  /** Job-catalog announcements from the 职位信息 page (module 1). */
  announcements: JobRow[]
  jdDocuments: DocumentSummary[]
  focusHint?: string
  presetAnnouncementId?: string
}>()

const emit = defineEmits<{
  (event: 'applied', resume: ResumeDetail): void
  (event: 'reverted', resume: ResumeDetail): void
}>()

type JdMode = 'announcement' | 'document' | 'text'

const initialAnnouncementId =
  props.presetAnnouncementId ||
  props.resume.target_announcement_id ||
  props.announcements[0]?.id ||
  ''

const mode = ref<JdMode>(
  props.announcements.length ? 'announcement' : props.jdDocuments.length ? 'document' : 'text',
)
const announcementId = ref(initialAnnouncementId)
const jdDocumentId = ref(props.jdDocuments[0]?.id || '')
const jdText = ref('')
const focus = ref('')
const generating = ref(false)
const applying = ref(false)
const loadingHistory = ref(false)
const optimization = ref<ResumeOptimization | null>(null)
const optimizations = ref<ResumeOptimizationSummary[]>([])
const selectedIds = ref<string[]>([])
const showDraft = ref(false)

const statusLabels: Record<OptimizationStatus, string> = {
  generated: '待应用',
  applied: '已应用',
  reverted: '已撤销',
  discarded: '已丢弃',
}

const kindLabels: Record<ResumeSuggestion['kind'], string> = {
  rewrite_bullet: '改写表述',
  add_bullet: '补充细节',
  add_skill: '补技能',
  add_section: '补章节',
  gap_plan: '技能补强',
}

const citationLabels: Record<string, string> = {
  resume_entry: '简历条目',
  resume_section: '简历章节',
  resume_head: '基本信息',
  job: '目标职位',
  announcement: '职位公告',
  jd_document: 'JD 文档',
  jd_text: '粘贴 JD',
}

const isStale = computed(
  () =>
    optimization.value !== null &&
    optimization.value.status === 'generated' &&
    optimization.value.base_content_version !== props.resume.content_version,
)

const canApply = computed(
  () => optimization.value?.status === 'generated' && !isStale.value && selectedIds.value.length > 0,
)

const applicableSuggestions = computed(
  () => optimization.value?.suggestions.filter((item) => item.applicable) || [],
)

const canGenerate = computed(() => {
  if (mode.value === 'announcement') return Boolean(announcementId.value)
  if (mode.value === 'document') return Boolean(jdDocumentId.value)
  return jdText.value.trim().length >= 20
})

async function loadHistory() {
  loadingHistory.value = true
  try {
    const result = await listResumeOptimizations(props.resume.id)
    optimizations.value = result.items
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    loadingHistory.value = false
  }
}

async function generate() {
  if (!canGenerate.value) {
    ElMessage.warning(
      mode.value === 'text' ? '请粘贴至少 20 个字符的岗位描述' : '请先选择目标职位或 JD 文档',
    )
    return
  }
  const payload: ResumeOptimizeInput = {}
  if (mode.value === 'announcement') payload.announcement_id = announcementId.value
  if (mode.value === 'document') payload.jd_document_id = jdDocumentId.value
  if (mode.value === 'text') payload.jd_text = jdText.value.trim()
  const focusValue = focus.value.trim() || props.focusHint?.trim() || ''
  if (focusValue) payload.focus = focusValue

  generating.value = true
  try {
    setOptimization(await optimizeResume(props.resume.id, payload))
    showDraft.value = false
    ElMessage.success('已生成匹配报告与建议稿')
    await loadHistory()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    generating.value = false
  }
}

function setOptimization(next: ResumeOptimization) {
  optimization.value = next
  selectedIds.value = next.suggestions.filter((item) => item.applicable).map((item) => item.id)
}

function toggle(suggestion: ResumeSuggestion) {
  if (!suggestion.applicable) return
  if (selectedIds.value.includes(suggestion.id)) {
    selectedIds.value = selectedIds.value.filter((id) => id !== suggestion.id)
  } else {
    selectedIds.value = [...selectedIds.value, suggestion.id]
  }
}

function selectAllApplicable() {
  selectedIds.value = applicableSuggestions.value.map((item) => item.id)
}

async function applySelected() {
  if (!optimization.value) return
  if (!selectedIds.value.length) {
    ElMessage.warning('请先勾选要写入简历的建议')
    return
  }
  applying.value = true
  try {
    const result = await applyResumeOptimization(
      props.resume.id,
      optimization.value.id,
      selectedIds.value,
    )
    setOptimization(result.optimization)
    ElMessage.success(`已应用 ${result.applied_suggestion_ids.length} 条建议到简历`)
    emit('applied', result.resume)
    await loadHistory()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    applying.value = false
  }
}

async function revertApplied(target: ResumeOptimization | ResumeOptimizationSummary) {
  try {
    const restored = await revertResumeOptimization(props.resume.id, target.id)
    ElMessage.success('已撤销应用，简历恢复到应用前的版本')
    emit('reverted', restored)
    await loadHistory()
    if (optimization.value?.id === target.id) {
      optimization.value = await getResumeOptimization(props.resume.id, target.id)
      selectedIds.value = []
    }
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

async function discard(target: ResumeOptimizationSummary) {
  try {
    await discardResumeOptimization(props.resume.id, target.id)
    ElMessage.success('已丢弃这次优化记录')
    await loadHistory()
    if (optimization.value?.id === target.id) optimization.value = null
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

async function openHistory(target: ResumeOptimizationSummary) {
  try {
    setOptimization(await getResumeOptimization(props.resume.id, target.id))
    showDraft.value = false
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

onMounted(loadHistory)
</script>

<template>
  <div class="optimize-panel">
    <section class="optimize-target">
      <div class="section-heading section-heading--compact">
        <div>
          <p class="eyebrow">TARGET JD</p>
          <h2>选择目标岗位或 JD</h2>
        </div>
        <span class="muted-note">匹配报告与建议都基于这份 JD</span>
      </div>
      <el-tabs v-model="mode">
        <el-tab-pane label="目标职位公告" name="announcement">
          <el-select
            v-model="announcementId"
            placeholder="选择职位信息里导入的公告"
            class="full-width"
            filterable
          >
            <el-option
              v-for="announcement in announcements"
              :key="announcement.id"
              :label="`${announcement.company.name} · ${announcement.title}`"
              :value="announcement.id"
            />
          </el-select>
          <p v-if="!announcements.length" class="muted-note">
            还没有职位公告，请先在「职位信息」里导入一条，或改用粘贴 JD。
          </p>
        </el-tab-pane>
        <el-tab-pane label="JD 文档" name="document">
          <el-select v-model="jdDocumentId" placeholder="选择知识库中的 JD" class="full-width">
            <el-option
              v-for="document in jdDocuments"
              :key="document.id"
              :label="document.display_name"
              :value="document.id"
            />
          </el-select>
          <p v-if="!jdDocuments.length" class="muted-note">
            知识库中还没有 JD 文档，可以在「知识库」导入，或直接粘贴 JD。
          </p>
        </el-tab-pane>
        <el-tab-pane label="粘贴 JD" name="text">
          <el-input
            v-model="jdText"
            type="textarea"
            :rows="6"
            placeholder="粘贴岗位描述与任职要求，例如：任职要求：熟悉 Python、FastAPI 与 RAG…"
          />
        </el-tab-pane>
      </el-tabs>
      <el-input
        v-model="focus"
        class="focus-input"
        placeholder="本次优化重点（可选），例如：突出 RAG 与评测经验"
        maxlength="300"
        clearable
      />
      <el-button
        type="primary"
        size="large"
        :icon="MagicStick"
        :loading="generating"
        :disabled="!canGenerate"
        class="full-button"
        @click="generate"
      >
        生成匹配报告与建议稿
      </el-button>
    </section>

    <template v-if="optimization">
      <section class="surface optimize-report">
        <div class="optimize-report-top">
          <div class="match-score">
            <span>匹配总分</span>
            <strong>{{ optimization.match_report.total_score }}</strong>
            <small>/ 100</small>
          </div>
          <div class="optimize-report-meta">
            <el-tag :type="optimization.match_report.eligible ? 'success' : 'danger'" size="large">
              {{ optimization.match_report.eligible ? '通过硬条件' : '未通过硬条件' }}
            </el-tag>
            <el-tag effect="plain">{{ statusLabels[optimization.status] }}</el-tag>
            <p class="muted-note">目标：{{ optimization.match_report.jd_title }}</p>
            <p v-if="optimization.match_report.hard_gate.reasons.length" class="muted-note">
              {{ optimization.match_report.hard_gate.reasons.join('；') }}
            </p>
            <p
              v-for="unknown in optimization.match_report.hard_gate.unknowns"
              :key="unknown"
              class="muted-note"
            >
              {{ unknown }}
            </p>
          </div>
        </div>

        <el-alert
          v-if="isStale"
          type="warning"
          :closable="false"
          show-icon
          title="简历在生成建议后已被修改"
          description="当前建议基于旧版本，请重新生成后再应用。"
        />

        <MatchScoreBreakdown :breakdown="optimization.match_report.breakdown" />

        <div class="optimize-tags">
          <div>
            <h3>已覆盖</h3>
            <div class="skill-list">
              <el-tag
                v-for="skill in optimization.match_report.matched_required_skills"
                :key="skill"
                type="success"
              >
                {{ skill }}
              </el-tag>
              <el-tag
                v-for="skill in optimization.match_report.matched_preferred_skills"
                :key="skill"
                type="info"
                effect="plain"
              >
                + {{ skill }}
              </el-tag>
              <span v-if="!optimization.match_report.matched_required_skills.length" class="muted-note">
                还没有命中必备技能
              </span>
            </div>
          </div>
          <div>
            <h3>缺口</h3>
            <div class="skill-list">
              <el-tag
                v-for="skill in optimization.match_report.missing_required_skills"
                :key="skill"
                type="danger"
                effect="plain"
              >
                {{ skill }}
              </el-tag>
              <span v-if="!optimization.match_report.missing_required_skills.length" class="muted-note">
                必备技能无缺口
              </span>
            </div>
          </div>
        </div>

        <div v-if="optimization.match_report.strengths.length" class="optimize-notes">
          <p v-for="item in optimization.match_report.strengths" :key="item">✓ {{ item }}</p>
        </div>
        <div v-if="optimization.match_report.gaps.length" class="optimize-notes optimize-notes--gap">
          <p v-for="item in optimization.match_report.gaps" :key="item">! {{ item }}</p>
        </div>
      </section>

      <section class="surface optimize-suggestions">
        <div class="section-heading section-heading--compact">
          <div>
            <p class="eyebrow">SUGGESTIONS</p>
            <h2>建议稿</h2>
          </div>
          <div class="suggestion-actions">
            <span class="muted-note">
              可应用 {{ optimization.applicable_count }} 条 · 需人工补充
              {{ optimization.requires_review_count }} 条
            </span>
            <el-button size="small" link @click="selectAllApplicable">全选可应用</el-button>
            <el-button size="small" link @click="showDraft = !showDraft">
              {{ showDraft ? '查看建议列表' : '预览建议稿' }}
            </el-button>
          </div>
        </div>

        <ResumePreview
          v-if="showDraft"
          :head="optimization.draft.head"
          :sections="optimization.draft.sections"
          :template="resume.template"
          :font-size="resume.font_size"
          :show-empty="false"
          caption="建议稿预览（尚未写入简历）"
        />

        <div v-else class="suggestion-list">
          <article
            v-for="suggestion in optimization.suggestions"
            :key="suggestion.id"
            class="suggestion-card"
            :class="{ 'suggestion-card--blocked': !suggestion.applicable }"
          >
            <div class="suggestion-head">
              <el-checkbox
                :model-value="selectedIds.includes(suggestion.id)"
                :disabled="!suggestion.applicable || optimization.status !== 'generated'"
                @change="toggle(suggestion)"
              />
              <div class="suggestion-title">
                <strong>{{ suggestion.title }}</strong>
                <div class="suggestion-badges">
                  <el-tag size="small" effect="plain">{{ kindLabels[suggestion.kind] }}</el-tag>
                  <el-tag
                    size="small"
                    :type="suggestion.priority === 'high' ? 'danger' : 'info'"
                    effect="plain"
                  >
                    {{ suggestion.priority === 'high' ? '高优先' : '一般' }}
                  </el-tag>
                  <el-tag v-if="!suggestion.applicable" size="small" type="warning" effect="plain">
                    需人工补充
                  </el-tag>
                </div>
              </div>
            </div>
            <p v-if="suggestion.original" class="suggestion-diff suggestion-diff--before">
              <span>原：</span>{{ suggestion.original }}
            </p>
            <p v-if="suggestion.proposed" class="suggestion-diff suggestion-diff--after">
              <span>改：</span>{{ suggestion.proposed }}
            </p>
            <p class="suggestion-rationale">{{ suggestion.rationale }}</p>
            <div class="suggestion-citations">
              <small
                v-for="(citation, index) in suggestion.citations"
                :key="`${suggestion.id}-${index}`"
              >
                {{ citationLabels[citation.source_type] || citation.source_type }}：{{
                  citation.quote
                }}
              </small>
            </div>
          </article>
        </div>

        <div class="optimize-footer">
          <el-button
            type="primary"
            :loading="applying"
            :disabled="!canApply"
            @click="applySelected"
          >
            应用 {{ selectedIds.length }} 条建议到简历
          </el-button>
          <el-button
            v-if="optimization.status === 'applied'"
            :icon="RefreshLeft"
            @click="revertApplied(optimization)"
          >
            撤销本次应用
          </el-button>
          <span class="muted-note">
            <template v-if="optimization.status === 'applied'">
              这次建议已经写入简历；撤销会恢复到应用前的版本。
            </template>
            <template v-else-if="optimization.status === 'reverted'">
              这次建议已撤销，可重新生成新的建议。
            </template>
            <template v-else>
              应用会写入简历并生成新版本；“需人工补充”的建议不会被自动写入。
            </template>
          </span>
        </div>
      </section>
    </template>

    <el-empty v-else description="选择或用粘贴 JD 后生成匹配报告，查看 AI 建议稿" />

    <section class="surface optimize-history">
      <div class="section-heading section-heading--compact">
        <div>
          <p class="eyebrow">HISTORY</p>
          <h2>优化记录</h2>
        </div>
        <span class="muted-note">每次生成都会保留可追溯版本</span>
      </div>
      <el-skeleton v-if="loadingHistory" :rows="3" animated />
      <el-empty v-else-if="!optimizations.length" description="还没有优化记录" :image-size="60" />
      <ul v-else class="history-list">
        <li v-for="item in optimizations" :key="item.id" class="history-row">
          <div>
            <strong>{{ item.jd_title }}</strong>
            <small>
              {{ new Date(item.created_at).toLocaleString() }} · 总分 {{ item.total_score }} ·
              {{ item.applicable_count }}/{{ item.suggestion_count }} 条可应用
            </small>
          </div>
          <div class="history-actions">
            <el-tag
              size="small"
              :type="item.status === 'applied' ? 'success' : item.status === 'generated' ? 'warning' : 'info'"
              effect="plain"
            >
              {{ statusLabels[item.status] }}
            </el-tag>
            <el-button size="small" link @click="openHistory(item)">查看</el-button>
            <el-button
              v-if="item.status === 'applied'"
              size="small"
              link
              @click="revertApplied(item)"
            >
              撤销
            </el-button>
            <el-button
              v-if="item.status === 'generated'"
              size="small"
              link
              @click="discard(item)"
            >
              丢弃
            </el-button>
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>
