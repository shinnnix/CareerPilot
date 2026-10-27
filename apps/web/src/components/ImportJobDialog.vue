<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'

import { getApiErrorMessage } from '@/api/errors'
import {
  confirmJobImport,
  importJobArticle,
  importJobFile,
  importJobText,
} from '@/api/workspace'
import type { JobAnnouncement, JobImportConfirmInput, JobImportRecord } from '@/types/workspace'
import { COMPANY_TYPES, RECRUITMENT_TYPES } from '@/types/workspace'

const props = defineProps<{ modelValue: boolean }>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'imported', announcement: JobAnnouncement): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const step = ref<'input' | 'review'>('input')
const mode = ref<'text' | 'article_url' | 'file'>('text')
const submitting = ref(false)
const errorMessage = ref('')
const selectedFile = ref<File | null>(null)
const sourceName = ref('')
const rawText = ref('')
const articleUrl = ref('')
const record = ref<JobImportRecord | null>(null)

const form = reactive({
  title: '',
  company_name: '',
  company_type: '',
  company_scale: '',
  industry: '',
  recruitment_type: '',
  target_cohort: '',
  deadline_text: '',
  deadline_at: '',
  announcement_url: '',
})

const locations = ref<string[]>([])
const positions = ref<string[]>([])
const confidence = ref<Record<string, string>>({})
const alternatives = ref<Record<string, { rule?: unknown; llm?: unknown }>>({})

const FIELD_LABELS: Record<string, string> = {
  title: '公告标题',
  company_name: '公司名称',
  recruitment_type: '招聘类型',
  target_cohort: '招聘对象',
  locations: '工作地点',
  positions: '岗位',
  deadline_text: '投递截止',
}

const conflictRows = computed(() =>
  Object.entries(alternatives.value).map(([field, pair]) => ({
    field,
    label: FIELD_LABELS[field] || field,
    rule: formatCandidate(pair.rule),
    llm: formatCandidate(pair.llm),
  })),
)

function formatCandidate(value: unknown): string {
  if (Array.isArray(value)) return value.join('、')
  if (value === null || value === undefined) return '—'
  return String(value)
}

watch(visible, (open) => {
  if (open) reset()
})

function reset() {
  step.value = 'input'
  mode.value = 'text'
  errorMessage.value = ''
  selectedFile.value = null
  sourceName.value = ''
  rawText.value = ''
  articleUrl.value = ''
  record.value = null
  Object.assign(form, {
    title: '',
    company_name: '',
    company_type: '',
    company_scale: '',
    industry: '',
    recruitment_type: '',
    target_cohort: '',
    deadline_text: '',
    deadline_at: '',
    announcement_url: '',
  })
  locations.value = []
  positions.value = []
  confidence.value = {}
  alternatives.value = {}
}

function handleFileChange(file: UploadFile) {
  selectedFile.value = file.raw || null
}

function lowConfidence(field: string): boolean {
  return confidence.value[field] === 'low'
}

function applyDraft(importRecord: JobImportRecord) {
  record.value = importRecord
  const draft = importRecord.parsed
  Object.assign(form, {
    title: draft.title || '',
    company_name: draft.company_name || '',
    company_type: '',
    company_scale: '',
    industry: '',
    recruitment_type: draft.recruitment_type || '',
    target_cohort: draft.target_cohort || '',
    deadline_text: draft.deadline_text || '',
    deadline_at: draft.deadline_at ? draft.deadline_at.slice(0, 10) : '',
    announcement_url: importRecord.source_url || '',
  })
  locations.value = [...(draft.locations || [])]
  positions.value = [...(draft.positions || [])]
  confidence.value = draft.confidence || {}
  alternatives.value = draft.alternatives || {}
  step.value = 'review'
}

async function runImport() {
  errorMessage.value = ''
  submitting.value = true
  try {
    if (mode.value === 'text') {
      if (rawText.value.trim().length < 20) {
        ElMessage.warning('公告正文至少需要 20 个字符')
        return
      }
      applyDraft(
        await importJobText({
          raw_text: rawText.value,
          source_name: sourceName.value || null,
        }),
      )
    } else if (mode.value === 'article_url') {
      if (!articleUrl.value.trim()) {
        ElMessage.warning('请粘贴公众号文章链接')
        return
      }
      applyDraft(
        await importJobArticle({
          url: articleUrl.value.trim(),
          source_name: sourceName.value || null,
        }),
      )
    } else {
      if (!selectedFile.value) {
        ElMessage.warning('请选择 TXT、Markdown 或 PDF 文件')
        return
      }
      applyDraft(await importJobFile(selectedFile.value))
    }
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  } finally {
    submitting.value = false
  }
}

async function submitConfirm() {
  if (!record.value) return
  if (form.title.trim().length < 2) {
    ElMessage.warning('请填写公告标题')
    return
  }
  if (!form.company_name.trim()) {
    ElMessage.warning('请填写公司名称')
    return
  }
  if (!positions.value.length) {
    ElMessage.warning('至少保留一个岗位，便于后续按岗位创建投递')
    return
  }

  const payload: JobImportConfirmInput = {
    title: form.title.trim(),
    company_name: form.company_name.trim(),
    company_type: form.company_type || null,
    company_scale: form.company_scale || null,
    industry: form.industry || null,
    recruitment_type: form.recruitment_type || null,
    target_cohort: form.target_cohort || null,
    locations: locations.value,
    positions: positions.value.map((title) => ({ title })),
    deadline_text: form.deadline_text || null,
    deadline_at: form.deadline_at || null,
    announcement_url: form.announcement_url || null,
    raw_text: record.value.raw_snapshot,
  }

  submitting.value = true
  errorMessage.value = ''
  try {
    const announcement = await confirmJobImport(record.value.id, payload)
    ElMessage.success('已加入职位信息')
    visible.value = false
    emit('imported', announcement)
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="导入职位" width="760px" top="6vh">
    <el-alert
      v-if="errorMessage"
      class="dialog-alert"
      :title="errorMessage"
      type="error"
      :closable="false"
      show-icon
    />

    <el-alert
      v-if="conflictRows.length"
      class="dialog-alert"
      type="warning"
      :closable="false"
      show-icon
      title="规则解析与模型抽取结果不一致，已保留规则值，请人工确认"
    >
      <ul class="conflict-list">
        <li v-for="row in conflictRows" :key="row.field">
          {{ row.label }}：规则「{{ row.rule }}」· 模型「{{ row.llm }}」
        </li>
      </ul>
    </el-alert>

    <template v-if="step === 'input'">
      <el-tabs v-model="mode" stretch>
        <el-tab-pane label="粘贴文本" name="text" />
        <el-tab-pane label="上传文件" name="file" />
        <el-tab-pane label="公众号文章链接" name="article_url" />
      </el-tabs>

      <el-form label-position="top" @submit.prevent="runImport">
        <el-form-item v-if="mode === 'text'" label="公告正文">
          <el-input
            v-model="rawText"
            type="textarea"
            :rows="12"
            placeholder="粘贴招聘公告原文，包含「招聘岗位 / 工作地点 / 截止时间」等信息，解析会更准确"
          />
        </el-form-item>

        <template v-else-if="mode === 'file'">
          <el-form-item label="选择文件">
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
        </template>

        <template v-else>
          <el-form-item label="公众号文章链接">
            <el-input
              v-model="articleUrl"
              placeholder="https://mp.weixin.qq.com/s/..."
              clearable
            />
          </el-form-item>
          <p class="panel-note">
            仅抓取你提供的单条文章，不做订阅、历史遍历或登录态抓取；正文只在本机保存，并保留原文链接。
          </p>
        </template>

        <el-form-item label="来源名称（可选）">
          <el-input v-model="sourceName" maxlength="200" placeholder="例如：XX校园招聘 公众号" />
        </el-form-item>
      </el-form>
    </template>

    <template v-else>
      <p class="panel-note">
        规则解析已完成，字段可修改；标记「请确认」的字段置信度较低。确认后写入职位信息。
      </p>
      <el-form label-position="top" @submit.prevent="submitConfirm">
        <el-form-item>
          <template #label>
            公告标题
            <el-tag v-if="lowConfidence('title')" size="small" type="warning" effect="plain">
              请确认
            </el-tag>
          </template>
          <el-input v-model="form.title" maxlength="300" />
        </el-form-item>
        <div class="form-grid">
          <el-form-item>
            <template #label>
              公司名称
              <el-tag
                v-if="lowConfidence('company_name')"
                size="small"
                type="warning"
                effect="plain"
              >
                请确认
              </el-tag>
            </template>
            <el-input v-model="form.company_name" maxlength="200" />
          </el-form-item>
          <el-form-item label="公司类型">
            <el-select v-model="form.company_type" clearable placeholder="未填写">
              <el-option v-for="item in COMPANY_TYPES" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
          <el-form-item label="招聘类型">
            <el-select v-model="form.recruitment_type" clearable placeholder="未识别">
              <el-option
                v-for="item in RECRUITMENT_TYPES"
                :key="item"
                :label="item"
                :value="item"
              />
            </el-select>
          </el-form-item>
          <el-form-item>
            <template #label>
              招聘对象
              <el-tag
                v-if="lowConfidence('target_cohort')"
                size="small"
                type="warning"
                effect="plain"
              >
                请确认
              </el-tag>
            </template>
            <el-input v-model="form.target_cohort" maxlength="20" placeholder="例如 2027届" />
          </el-form-item>
          <el-form-item label="公司规模">
            <el-input v-model="form.company_scale" maxlength="50" placeholder="例如 1000-5000人" />
          </el-form-item>
          <el-form-item label="投递截止">
            <el-input v-model="form.deadline_text" maxlength="100" placeholder="招满为止 / 2026-11-30" />
          </el-form-item>
          <el-form-item label="截止日期（可选）">
            <el-date-picker
              v-model="form.deadline_at"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择日期"
            />
          </el-form-item>
          <el-form-item label="原文链接（可选）">
            <el-input v-model="form.announcement_url" placeholder="https://..." />
          </el-form-item>
        </div>

        <el-form-item label="工作地点">
          <el-select
            v-model="locations"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入后回车添加，可多个"
          />
        </el-form-item>

        <el-form-item label="招聘岗位">
          <el-select
            v-model="positions"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入后回车添加，可多个"
          />
        </el-form-item>
      </el-form>

      <el-collapse>
        <el-collapse-item title="查看原文快照" name="raw">
          <pre class="raw-snapshot">{{ record?.raw_snapshot }}</pre>
        </el-collapse-item>
      </el-collapse>
    </template>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button v-if="step === 'review'" @click="step = 'input'">上一步</el-button>
      <el-button
        v-if="step === 'input'"
        type="primary"
        :loading="submitting"
        @click="runImport"
      >
        解析公告
      </el-button>
      <el-button v-else type="primary" :loading="submitting" @click="submitConfirm">
        确认入库
      </el-button>
    </template>
  </el-dialog>
</template>
