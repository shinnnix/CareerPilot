<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { DocumentAdd, UploadFilled } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

import { importTextDocument, listDocuments, uploadDocument } from '@/api/documents'
import { getApiErrorMessage } from '@/api/errors'
import type { DocumentSummary, DocumentType } from '@/types/documents'

const router = useRouter()
const documents = ref<DocumentSummary[]>([])
const loading = ref(false)
const submitting = ref(false)
const errorMessage = ref('')
const importMode = ref<'text' | 'file'>('text')
const selectedFile = ref<File | null>(null)

const form = reactive({
  display_name: '',
  document_type: 'job_description' as DocumentType,
  raw_text: '',
})

const pendingCount = computed(
  () => documents.value.filter((document) => document.review_status === 'pending').length,
)
const totalChunks = computed(() =>
  documents.value.reduce((total, document) => total + document.chunk_count, 0),
)

const typeLabels: Record<DocumentType, string> = {
  resume: '简历',
  job_description: '职位 JD',
  learning_note: '学习笔记',
  other: '其他资料',
}

async function loadDocuments() {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await listDocuments({ page_size: 100 })
    documents.value = result.items
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  } finally {
    loading.value = false
  }
}

function handleFileChange(file: UploadFile) {
  selectedFile.value = file.raw || null
  if (!form.display_name && file.name) {
    form.display_name = file.name.replace(/\.[^.]+$/, '')
  }
}

async function submitImport() {
  if (!form.display_name.trim()) {
    ElMessage.warning('请填写文档名称')
    return
  }
  if (importMode.value === 'text' && form.raw_text.trim().length < 20) {
    ElMessage.warning('正文至少需要 20 个字符')
    return
  }
  if (importMode.value === 'file' && !selectedFile.value) {
    ElMessage.warning('请选择 TXT、Markdown 或 PDF 文件')
    return
  }

  submitting.value = true
  try {
    const document = importMode.value === 'text'
      ? await importTextDocument({ ...form })
      : await uploadDocument({
          display_name: form.display_name,
          document_type: form.document_type,
          file: selectedFile.value as File,
        })
    ElMessage.success(`已生成 ${document.chunk_count} 个标题感知 Chunk`)
    await router.push(`/knowledge/${document.id}`)
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

function confidencePercent(document: DocumentSummary): number {
  return Math.round(Number(document.parse_confidence) * 100)
}

onMounted(loadDocuments)
</script>

<template>
  <main class="page">
    <section class="knowledge-hero">
      <div>
        <p class="eyebrow">WEEK 2 · KNOWLEDGE INGESTION</p>
        <h1>看见文档如何变成<br />可检索的知识单元</h1>
        <p class="hero-copy">
          原文、结构化字段和 Chunk 同时保留。当前使用可解释规则解析，所有结果都可人工确认。
        </p>
      </div>
      <div class="knowledge-stats">
        <div><strong>{{ documents.length }}</strong><span>文档</span></div>
        <div><strong>{{ totalChunks }}</strong><span>Chunks</span></div>
        <div><strong>{{ pendingCount }}</strong><span>待确认</span></div>
      </div>
    </section>

    <div class="knowledge-layout">
      <section class="surface import-panel">
        <div class="section-heading section-heading--compact">
          <div>
            <p class="eyebrow">IMPORT</p>
            <h2>导入私人资料</h2>
          </div>
        </div>
        <el-tabs v-model="importMode" stretch>
          <el-tab-pane label="粘贴文本" name="text" />
          <el-tab-pane label="上传文件" name="file" />
        </el-tabs>
        <el-form label-position="top" @submit.prevent="submitImport">
          <el-form-item label="资料类型">
            <el-select v-model="form.document_type">
              <el-option
                v-for="(label, value) in typeLabels"
                :key="value"
                :label="label"
                :value="value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="文档名称">
            <el-input v-model="form.display_name" placeholder="例如：我的中文简历 v2" />
          </el-form-item>
          <el-form-item v-if="importMode === 'text'" label="文档原文">
            <el-input
              v-model="form.raw_text"
              type="textarea"
              :rows="11"
              placeholder="建议保留岗位职责、任职要求、项目经历等标题……"
            />
          </el-form-item>
          <el-form-item v-else label="选择文件">
            <el-upload
              drag
              :auto-upload="false"
              :limit="1"
              accept=".txt,.md,.pdf"
              :on-change="handleFileChange"
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">拖入文件或 <em>点击选择</em></div>
              <template #tip>
                <div class="el-upload__tip">支持 TXT、Markdown、文本型 PDF，最大 2 MiB</div>
              </template>
            </el-upload>
          </el-form-item>
          <el-button
            type="primary"
            size="large"
            :icon="DocumentAdd"
            :loading="submitting"
            class="full-button"
            @click="submitImport"
          >
            解析并建立 Chunk
          </el-button>
        </el-form>
      </section>

      <section>
        <div class="section-heading section-heading--compact">
          <div>
            <p class="eyebrow">DOCUMENTS</p>
            <h2>知识库资料</h2>
          </div>
          <span>{{ documents.length }} 份</span>
        </div>

        <el-skeleton v-if="loading" :rows="8" animated class="surface" />
        <el-alert
          v-else-if="errorMessage"
          :title="errorMessage"
          type="error"
          :closable="false"
          show-icon
        />
        <el-empty v-else-if="documents.length === 0" description="还没有导入资料" />
        <div v-else class="document-list">
          <RouterLink
            v-for="document in documents"
            :key="document.id"
            :to="`/knowledge/${document.id}`"
            class="document-row"
          >
            <div class="document-icon">{{ typeLabels[document.document_type].slice(0, 1) }}</div>
            <div class="document-main">
              <div>
                <h3>{{ document.display_name }}</h3>
                <el-tag
                  size="small"
                  :type="document.review_status === 'confirmed' ? 'success' : 'warning'"
                  effect="plain"
                >
                  {{ document.review_status === 'confirmed' ? '已确认' : '待确认' }}
                </el-tag>
              </div>
              <p>
                {{ typeLabels[document.document_type] }} · {{ document.chunk_count }} Chunks ·
                {{ document.index_version }}
              </p>
              <div class="confidence-line">
                <span>规则解析置信度</span>
                <el-progress
                  :percentage="confidencePercent(document)"
                  :stroke-width="5"
                  :show-text="false"
                />
                <strong>{{ confidencePercent(document) }}%</strong>
              </div>
            </div>
            <span class="row-arrow">→</span>
          </RouterLink>
        </div>
      </section>
    </div>
  </main>
</template>

