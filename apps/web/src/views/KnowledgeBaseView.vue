<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { DocumentAdd, UploadFilled } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

import { importTextDocument, listDocuments, uploadDocument } from '@/api/documents'
import { getApiErrorCode, getApiErrorDetails, getApiErrorMessage } from '@/api/errors'
import { importResumeText, uploadResumeFile } from '@/api/resumes'
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
  document_type: 'learning_note' as DocumentType,
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

/**
 * Plan §5.4: JD 原文统一从「职位信息 → 导入职位」进入，这里不再提供手工录入入口。
 * `job_description` 仅用于展示历史数据。
 */
const importTypes: DocumentType[] = ['resume', 'learning_note', 'other']

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
    if (form.document_type === 'resume') {
      // Resume uploads now continue into the editable resume workspace instead
      // of stopping at a raw knowledge document.
      const resume = importMode.value === 'text'
        ? await importResumeText({
            display_name: form.display_name,
            raw_text: form.raw_text,
          })
        : await uploadResumeFile({
            display_name: form.display_name,
            file: selectedFile.value as File,
          })
      ElMessage.success('已解析为可编辑简历，可继续生成 AI 优化建议')
      await router.push(`/workspace/resumes/${resume.id}`)
      return
    }
    const document = importMode.value === 'text'
      ? await importTextDocument({ ...form })
      : await uploadDocument({
          display_name: form.display_name,
          document_type: form.document_type,
          file: selectedFile.value as File,
        })
    ElMessage.success(`已生成 ${document.chunk_count} 个标题感知 Chunk`)
    await router.push(`/workspace/library/${document.id}`)
  } catch (error) {
    if (getApiErrorCode(error) === 'RESUME_EXISTS') {
      const resumeId = getApiErrorDetails(error).resume_id
      if (typeof resumeId === 'string') {
        ElMessage.info('该简历已经建立过工作台，正在打开已有版本')
        await router.push(`/workspace/resumes/${resumeId}`)
        return
      }
    }
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
    <header class="page-head">
      <div>
        <p class="eyebrow">更多工具</p>
        <h1>资料库</h1>
        <p class="page-desc">
          证据底座：简历原文、项目材料、学习笔记的规范化文本与 Chunk。
          证据检索、简历优化引用、匹配解释都从这里取证据，改一处、处处一致。
        </p>
      </div>
      <div class="knowledge-stats">
        <div><strong>{{ documents.length }}</strong><span>文档</span></div>
        <div><strong>{{ totalChunks }}</strong><span>Chunks</span></div>
        <div><strong>{{ pendingCount }}</strong><span>待确认</span></div>
      </div>
    </header>

    <div class="knowledge-layout">
      <section class="surface import-panel">
        <div class="section-heading section-heading--compact">
          <div>
            <p class="eyebrow">导入</p>
            <h2>导入自己的材料</h2>
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
                v-for="value in importTypes"
                :key="value"
                :label="typeLabels[value]"
                :value="value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="资料名称">
            <el-input v-model="form.display_name" placeholder="例如：我的中文简历 v2" />
          </el-form-item>
          <el-alert
            v-if="form.document_type === 'resume'"
            class="inline-alert"
            type="info"
            :closable="false"
            show-icon
            title="简历将进入简历工作台"
            description="上传后会按章节拆成可编辑结构，可直接针对目标岗位/JD 生成匹配报告与建议稿。"
          />
          <el-form-item v-if="importMode === 'text'" label="原文">
            <el-input
              v-model="form.raw_text"
              type="textarea"
              :rows="11"
              placeholder="保留原文标题与段落，例如「项目经历」「课程笔记」……"
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
            {{ form.document_type === 'resume' ? '解析并生成简历工作台' : '解析并建立 Chunk' }}
          </el-button>
        </el-form>
      </section>

      <section>
        <div class="section-heading section-heading--compact">
          <div>
            <p class="eyebrow">资料清单</p>
            <h2>已导入的资料</h2>
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
            :to="`/workspace/library/${document.id}`"
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

