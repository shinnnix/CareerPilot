<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Delete, MagicStick, Refresh, Select } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'

import {
  correctDocument,
  deleteDocument,
  getDocument,
  getDocumentChunks,
  reindexDocument,
} from '@/api/documents'
import { getApiErrorCode, getApiErrorDetails, getApiErrorMessage } from '@/api/errors'
import { createResumeFromDocument } from '@/api/resumes'
import DocumentChunkCard from '@/components/DocumentChunkCard.vue'
import type {
  DocumentChunk,
  DocumentDetail,
  ExtractedDocumentData,
} from '@/types/documents'

const route = useRoute()
const router = useRouter()
const document = ref<DocumentDetail | null>(null)
const chunks = ref<DocumentChunk[]>([])
const loading = ref(true)
const saving = ref(false)
const reindexing = ref(false)
const errorMessage = ref('')
const skillsText = ref('')

const correction = reactive<ExtractedDocumentData>({
  title: null,
  company_name: null,
  city: null,
  email: null,
  phone: null,
  skills: [],
  section_titles: [],
  desired_cities: [],
  available_days_per_week: null,
  available_months: null,
})

const documentId = computed(() => String(route.params.id))
const confidence = computed(() => Math.round(Number(document.value?.parse_confidence || 0) * 100))

function syncCorrection() {
  if (!document.value) return
  Object.assign(correction, document.value.extracted_data)
  correction.skills = [...document.value.extracted_data.skills]
  correction.section_titles = [...document.value.extracted_data.section_titles]
  correction.desired_cities = [...document.value.extracted_data.desired_cities]
  skillsText.value = correction.skills.join(', ')
}

async function loadAll() {
  loading.value = true
  errorMessage.value = ''
  try {
    const [detail, chunkResult] = await Promise.all([
      getDocument(documentId.value),
      getDocumentChunks(documentId.value),
    ])
    document.value = detail
    chunks.value = chunkResult.items
    syncCorrection()
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  } finally {
    loading.value = false
  }
}

function parseSkills(): string[] {
  return [...new Set(skillsText.value.split(/[,，\n]/).map((item) => item.trim()).filter(Boolean))]
}

async function saveCorrection() {
  if (!document.value) return
  saving.value = true
  try {
    correction.skills = parseSkills()
    document.value = await correctDocument(documentId.value, {
      extracted_data: { ...correction },
    })
    syncCorrection()
    ElMessage.success('结构化字段已人工确认')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    saving.value = false
  }
}

async function handleReindex() {
  reindexing.value = true
  try {
    await reindexDocument(documentId.value)
    await loadAll()
    ElMessage.success('已使用当前解析器重新生成 Chunk，请重新确认字段')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    reindexing.value = false
  }
}

async function openResumeWorkspace() {
  if (!document.value) return
  try {
    const resume = await createResumeFromDocument({
      document_id: document.value.id,
      title: document.value.display_name,
    })
    ElMessage.success('已生成可编辑简历工作台')
    await router.push(`/workspace/resumes/${resume.id}`)
  } catch (error) {
    if (getApiErrorCode(error) === 'RESUME_EXISTS') {
      const resumeId = getApiErrorDetails(error).resume_id
      if (typeof resumeId === 'string') {
        await router.push(`/workspace/resumes/${resumeId}`)
        return
      }
    }
    ElMessage.error(getApiErrorMessage(error))
  }
}

async function handleDelete() {
  const confirmed = await ElMessageBox.confirm(
    '将同时删除原文、结构化字段和所有 Chunk，确认继续吗？',
    '删除知识库文档',
    { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' },
  ).then(() => true).catch(() => false)
  if (!confirmed) return
  try {
    await deleteDocument(documentId.value)
    ElMessage.success('知识库文档已删除')
    await router.push('/workspace/library')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

onMounted(loadAll)
</script>

<template>
  <main class="page">
    <RouterLink class="back-link" to="/workspace/library">
      <el-icon><ArrowLeft /></el-icon>
      返回知识库
    </RouterLink>

    <el-skeleton v-if="loading" :rows="12" animated class="surface" />
    <el-result
      v-else-if="errorMessage"
      icon="error"
      title="无法加载文档"
      :sub-title="errorMessage"
    />

    <template v-else-if="document">
      <section class="document-detail-hero">
        <div>
          <div class="document-badges">
            <el-tag effect="dark">{{ document.document_type }}</el-tag>
            <el-tag
              :type="document.review_status === 'confirmed' ? 'success' : 'warning'"
              effect="plain"
            >
              {{ document.review_status === 'confirmed' ? '人工已确认' : '等待人工确认' }}
            </el-tag>
            <el-tag v-if="document.prompt_injection_detected" type="danger" effect="dark">
              已隔离，不参与 RAG
            </el-tag>
          </div>
          <h1>{{ document.display_name }}</h1>
          <p>
            {{ document.parse_version }} → {{ document.index_version }} ·
            {{ document.chunk_count }} 个 Chunk
          </p>
        </div>
        <div class="detail-actions">
          <el-button
            v-if="document.document_type === 'resume'"
            type="primary"
            :icon="MagicStick"
            @click="openResumeWorkspace"
          >
            打开简历工作台
          </el-button>
          <el-button :icon="Refresh" :loading="reindexing" @click="handleReindex">
            重新解析
          </el-button>
          <el-button type="danger" plain :icon="Delete" @click="handleDelete">删除</el-button>
        </div>
      </section>

      <div class="document-detail-grid">
        <section class="surface correction-panel">
          <div class="section-heading section-heading--compact">
            <div>
              <p class="eyebrow">HUMAN REVIEW</p>
              <h2>结构化字段确认</h2>
            </div>
            <div class="confidence-badge">
              <span>解析置信度</span>
              <strong>{{ confidence }}%</strong>
            </div>
          </div>
          <p class="panel-note">
            置信度表示规则解析覆盖度；人工确认单独记录，不会把该数值伪造为 100%。
          </p>
          <el-alert
            v-if="document.prompt_injection_detected"
            title="检测到疑似提示词注入"
            :description="`安全标记：${document.security_flags.join('、')}。原文仍可审查，但不会建立向量或进入检索。`"
            type="error"
            show-icon
            :closable="false"
          />
          <el-form label-position="top">
            <div class="form-grid">
              <el-form-item label="标题/目标岗位">
                <el-input v-model="correction.title" clearable />
              </el-form-item>
              <el-form-item label="公司">
                <el-input v-model="correction.company_name" clearable />
              </el-form-item>
              <el-form-item label="城市">
                <el-input v-model="correction.city" clearable />
              </el-form-item>
              <el-form-item label="邮箱">
                <el-input v-model="correction.email" clearable />
              </el-form-item>
              <el-form-item label="电话">
                <el-input v-model="correction.phone" clearable />
              </el-form-item>
              <el-form-item label="识别章节">
                <el-input :model-value="correction.section_titles.join('、')" disabled />
              </el-form-item>
              <el-form-item label="期望城市（简历）">
                <el-input
                  :model-value="correction.desired_cities.join('、')"
                  placeholder="上海、杭州"
                  @update:model-value="correction.desired_cities = String($event).split(/[、,，]/).map((item) => item.trim()).filter(Boolean)"
                />
              </el-form-item>
              <el-form-item label="每周可到岗天数">
                <el-input-number v-model="correction.available_days_per_week" :min="1" :max="7" />
              </el-form-item>
              <el-form-item label="可实习月数">
                <el-input-number v-model="correction.available_months" :min="1" :max="36" />
              </el-form-item>
            </div>
            <el-form-item label="规范化技能（逗号分隔）">
              <el-input v-model="skillsText" type="textarea" :rows="3" />
            </el-form-item>
            <el-button
              type="primary"
              :icon="Select"
              :loading="saving"
              @click="saveCorrection"
            >
              确认结构化字段
            </el-button>
          </el-form>
        </section>

        <aside class="document-meta surface">
          <p class="eyebrow">PROVENANCE</p>
          <h2>可追溯信息</h2>
          <dl class="fact-list">
            <div><dt>文件</dt><dd>{{ document.file_name || '粘贴文本' }}</dd></div>
            <div><dt>大小</dt><dd>{{ document.source_size_bytes }} bytes</dd></div>
            <div><dt>Hash</dt><dd class="mono">{{ document.content_hash.slice(0, 12) }}…</dd></div>
            <div><dt>解析器</dt><dd>{{ document.parse_version }}</dd></div>
            <div><dt>索引版本</dt><dd>{{ document.index_version }}</dd></div>
            <div><dt>Embedding</dt><dd>{{ chunks[0]?.embedding_model || '尚未建立' }}</dd></div>
          </dl>
        </aside>
      </div>

      <section class="raw-section surface">
        <el-collapse>
          <el-collapse-item title="查看保存的规范化原文" name="raw">
            <pre>{{ document.raw_text }}</pre>
          </el-collapse-item>
        </el-collapse>
      </section>

      <section class="chunks-section">
        <div class="section-heading">
          <div>
            <p class="eyebrow">TITLE-AWARE CHUNKS</p>
            <h2>分块结果</h2>
          </div>
          <span>{{ chunks.length }} 个检索单元</span>
        </div>
        <div class="chunk-list">
          <DocumentChunkCard v-for="chunk in chunks" :key="chunk.id" :chunk="chunk" />
        </div>
      </section>
    </template>
  </main>
</template>
