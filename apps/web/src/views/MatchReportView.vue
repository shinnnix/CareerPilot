<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { useRoute } from 'vue-router'

import { listDocuments } from '@/api/documents'
import { getApiErrorMessage } from '@/api/errors'
import { buildMatchReport } from '@/api/retrieval'
import { generatePersonalization, saveMatchFeedback } from '@/api/applications'
import type { DocumentSummary } from '@/types/documents'
import type { MatchReport } from '@/types/retrieval'
import MatchScoreBreakdown from '@/components/MatchScoreBreakdown.vue'
import type { PersonalizationResult } from '@/types/applications'

const route = useRoute()
const resumes = ref<DocumentSummary[]>([])
const selectedResume = ref('')
const loading = ref(false)
const report = ref<MatchReport | null>(null)
const personalization = ref<PersonalizationResult | null>(null)
const generating = ref(false)
const jobId = computed(() => String(route.params.id))

async function loadResumes() {
  try {
    const response = await listDocuments({ document_type: 'resume', page_size: 100 })
    resumes.value = response.items
    selectedResume.value = response.items[0]?.id || ''
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

async function calculate() {
  if (!selectedResume.value) return
  loading.value = true
  try {
    report.value = await buildMatchReport(jobId.value, selectedResume.value)
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function generateMaterials() {
  if (!selectedResume.value) return
  generating.value = true
  try {
    personalization.value = await generatePersonalization(jobId.value, selectedResume.value)
    ElMessage.success('已生成经过引用校验的个性化材料')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    generating.value = false
  }
}

async function feedback(relevant: boolean) {
  try {
    await saveMatchFeedback(jobId.value, { relevant })
    ElMessage.success('反馈已保存，将用于后续评测')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

onMounted(loadResumes)
</script>

<template>
  <main class="page page--narrow">
    <RouterLink class="back-link" :to="`/workspace/jobs/${jobId}`">
      <el-icon><ArrowLeft /></el-icon>返回职位
    </RouterLink>
    <section class="match-hero">
      <div>
        <p class="eyebrow">EXPLAINABLE MATCH</p>
        <h1>职位匹配报告</h1>
        <p>硬条件先判断资格，分项得分只由可复现规则与检索证据计算。</p>
      </div>
      <div class="match-picker">
        <el-select v-model="selectedResume" placeholder="选择简历" size="large">
          <el-option v-for="resume in resumes" :key="resume.id" :label="resume.display_name" :value="resume.id" />
        </el-select>
        <el-button type="primary" size="large" :loading="loading" :disabled="!selectedResume" @click="calculate">
          计算匹配
        </el-button>
      </div>
    </section>
    <el-empty v-if="!resumes.length" description="请先在知识库导入一份简历" />

    <template v-if="report">
      <section class="match-summary surface">
        <div class="match-score">
          <span>总分</span><strong>{{ report.total_score }}</strong><small>/ 100</small>
        </div>
        <div>
          <el-tag :type="report.eligible ? 'success' : 'danger'" size="large">
            {{ report.eligible ? '通过硬条件' : '未通过硬条件' }}
          </el-tag>
          <p v-if="report.hard_gate.reasons.length">{{ report.hard_gate.reasons.join('；') }}</p>
          <p v-else>城市、每周到岗天数与实习周期未发现冲突。</p>
        </div>
        <div class="match-actions">
          <el-button :loading="generating" type="primary" @click="generateMaterials">生成申请材料</el-button>
          <el-button @click="feedback(true)">匹配准确</el-button>
          <el-button @click="feedback(false)">匹配不准</el-button>
        </div>
      </section>

      <section class="match-grid">
        <div class="surface">
          <p class="eyebrow">SCORE BREAKDOWN</p>
          <h2>分数来源</h2>
          <MatchScoreBreakdown :breakdown="report.breakdown" />
        </div>
        <div class="surface">
          <p class="eyebrow">SKILL GAP</p>
          <h2>技能缺口</h2>
          <h3>已覆盖</h3>
          <div class="skill-list">
            <el-tag v-for="skill in report.matched_required_skills" :key="skill" type="success">{{ skill }}</el-tag>
          </div>
          <h3>需要补强</h3>
          <div class="skill-list">
            <el-tag v-for="skill in report.missing_required_skills" :key="skill" type="danger" effect="plain">{{ skill }}</el-tag>
            <span v-if="!report.missing_required_skills.length">无必备技能缺口</span>
          </div>
        </div>
      </section>

      <section class="evidence-section">
        <div class="section-heading"><div><p class="eyebrow">EVIDENCE</p><h2>简历证据</h2></div></div>
        <article v-for="evidence in report.evidence" :key="evidence.chunk_id" class="surface evidence-card">
          <strong>{{ evidence.section_path.join(' / ') }}</strong>
          <p>{{ evidence.expanded_content || evidence.content }}</p>
          <RouterLink :to="`/workspace/library/${evidence.document_id}`">查看原始 Chunk →</RouterLink>
        </article>
      </section>

      <section v-if="personalization" class="personalization-section">
        <div class="section-heading"><div><p class="eyebrow">PERSONALIZATION</p><h2>引用校验后的申请准备</h2></div></div>
        <div class="match-grid">
          <article class="surface">
            <h3>简历事实要点</h3>
            <div v-for="item in personalization.resume_bullets.content" :key="item.text" class="artifact-item">
              <p>{{ item.text }}</p>
              <small v-for="citation in item.citations" :key="citation.source_id">证据：{{ citation.quote }}</small>
            </div>
          </article>
          <article class="surface">
            <h3>技能补强计划</h3>
            <div v-for="item in personalization.skill_gap_plan.content" :key="item.text" class="artifact-item">
              <p>{{ item.text }}</p>
              <small v-for="citation in item.citations" :key="citation.source_id">依据：{{ citation.quote }}</small>
            </div>
          </article>
        </div>
      </section>
    </template>
  </main>
</template>
