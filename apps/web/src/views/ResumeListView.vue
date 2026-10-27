<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { Delete, Plus, UploadFilled } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

import { getApiErrorCode, getApiErrorDetails, getApiErrorMessage } from '@/api/errors'
import { listJobCatalog } from '@/api/workspace'
import {
  createManualResume,
  deleteResume,
  importResumeText,
  listResumes,
  uploadResumeFile,
} from '@/api/resumes'
import ResumeTemplatePicker from '@/components/ResumeTemplatePicker.vue'
import type { ResumeSummary, ResumeTemplate } from '@/types/resumes'
import type { JobRow } from '@/types/workspace'

const PAGE_SIZE = 20

const templateLabels: Record<ResumeTemplate, string> = {
  classic: '经典简约',
  modern: '现代商务',
  elegant: '雅致居中',
  compact: '紧凑黑白',
}

const router = useRouter()
const resumes = ref<ResumeSummary[]>([])
const announcements = ref<JobRow[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const errorMessage = ref('')
const submitting = ref(false)

const importOpen = ref(false)
const importMode = ref<'text' | 'file'>('text')
const selectedFile = ref<File | null>(null)
const importForm = reactive({
  display_name: '',
  raw_text: '',
  template: 'classic' as ResumeTemplate,
  target_announcement_id: '' as string,
})

const manualOpen = ref(false)
const manualForm = reactive({
  title: '',
  template: 'classic' as ResumeTemplate,
  target_announcement_id: '' as string,
})

const announcementMap = computed(
  () =>
    new Map(
      announcements.value.map((row) => [row.id, `${row.company.name} · ${row.title}`]),
    ),
)

function templateLabel(value: string): string {
  return templateLabels[value as ResumeTemplate] || value
}

function formatTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  const pad = (input: number) => String(input).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`
}

async function loadAll() {
  loading.value = true
  errorMessage.value = ''
  try {
    const [resumeResult, catalogResult] = await Promise.all([
      listResumes({ page: page.value, page_size: PAGE_SIZE }),
      listJobCatalog({ page_size: 100 }),
    ])
    resumes.value = resumeResult.items
    total.value = resumeResult.total
    announcements.value = catalogResult.items
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  } finally {
    loading.value = false
  }
}

function handlePageChange(next: number) {
  page.value = next
  void loadAll()
}

function openResume(row: ResumeSummary) {
  void router.push(`/workspace/resumes/${row.id}`)
}

function openImport() {
  importMode.value = 'text'
  selectedFile.value = null
  importOpen.value = true
}

function openManual() {
  manualForm.title = ''
  manualForm.template = 'classic'
  manualForm.target_announcement_id = ''
  manualOpen.value = true
}

function handleFileChange(file: UploadFile) {
  selectedFile.value = file.raw || null
  if (!importForm.display_name && file.name) {
    importForm.display_name = file.name.replace(/\.[^.]+$/, '')
  }
}

async function goToExistingResume(error: unknown): Promise<boolean> {
  if (getApiErrorCode(error) !== 'RESUME_EXISTS') return false
  const resumeId = getApiErrorDetails(error).resume_id
  if (typeof resumeId !== 'string') return false
  ElMessage.info('该简历已经建立过工作台，正在打开已有版本')
  await router.push(`/workspace/resumes/${resumeId}`)
  return true
}

async function submitImport() {
  if (!importForm.display_name.trim()) {
    ElMessage.warning('请填写简历名称')
    return
  }
  if (importMode.value === 'text' && importForm.raw_text.trim().length < 20) {
    ElMessage.warning('简历正文至少需要 20 个字符')
    return
  }
  if (importMode.value === 'file' && !selectedFile.value) {
    ElMessage.warning('请选择 TXT、Markdown 或 PDF 简历文件')
    return
  }

  submitting.value = true
  try {
    const resume = importMode.value === 'text'
      ? await importResumeText({
          display_name: importForm.display_name,
          raw_text: importForm.raw_text,
          template: importForm.template,
          target_announcement_id: importForm.target_announcement_id || null,
        })
      : await uploadResumeFile({
          display_name: importForm.display_name,
          file: selectedFile.value as File,
          template: importForm.template,
          target_announcement_id: importForm.target_announcement_id || null,
        })
    importOpen.value = false
    ElMessage.success('已解析为可编辑简历')
    await router.push(`/workspace/resumes/${resume.id}`)
  } catch (error) {
    if (await goToExistingResume(error)) return
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

async function submitManual() {
  if (!manualForm.title.trim()) {
    ElMessage.warning('请填写简历名称')
    return
  }
  submitting.value = true
  try {
    const resume = await createManualResume({
      title: manualForm.title.trim(),
      template: manualForm.template,
      target_announcement_id: manualForm.target_announcement_id || null,
    })
    manualOpen.value = false
    ElMessage.success('已创建空白简历，开始填写吧')
    await router.push(`/workspace/resumes/${resume.id}`)
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: ResumeSummary) {
  const confirmed = await ElMessageBox.confirm(
    `将删除「${row.title}」和它的全部优化记录，知识库原文会保留，确认继续吗？`,
    '删除简历',
    { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' },
  )
    .then(() => true)
    .catch(() => false)
  if (!confirmed) return
  try {
    await deleteResume(row.id)
    ElMessage.success('简历已删除')
    if (resumes.value.length === 1 && page.value > 1) page.value -= 1
    await loadAll()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

onMounted(loadAll)
</script>

<template>
  <main class="page">
    <header class="page-head">
      <div>
        <p class="eyebrow">我的简历</p>
        <h1>每一份简历，都为目标而写</h1>
        <p class="page-desc">
          导入或新建简历，实时预览四套模板，按目标岗位生成优化建议。
        </p>
      </div>
      <div class="page-head-actions">
        <el-button :icon="Plus" @click="openManual">新建空白简历</el-button>
        <el-button type="primary" :icon="UploadFilled" @click="openImport">导入简历</el-button>
      </div>
    </header>

    <div class="data-bar">
      <span><strong>{{ total }}</strong> 份简历</span>
      <span class="data-bar-sep">·</span>
      <span>本页 {{ resumes.length }} 份</span>
      <span class="data-bar-note">选一份简历，开始针对目标岗位优化</span>
    </div>

    <section class="surface table-card">
      <div class="table-card-head">
        <h2>我的简历</h2>
        <span class="muted-note">共 {{ total }} 份</span>
      </div>

      <el-skeleton v-if="loading" :rows="6" animated class="table-card-state" />

      <el-alert
        v-else-if="errorMessage"
        class="table-card-state"
        :title="errorMessage"
        type="error"
        :closable="false"
        show-icon
      >
        <el-button size="small" @click="loadAll">重新加载</el-button>
      </el-alert>

      <el-empty v-else-if="!resumes.length" description="还没有简历">
        <el-button :icon="Plus" @click="openManual">新建空白简历</el-button>
        <el-button type="primary" :icon="UploadFilled" @click="openImport">导入简历</el-button>
      </el-empty>

      <template v-else>
        <el-table :data="resumes" class="resume-table" @row-click="openResume">
          <el-table-column label="名称" min-width="190">
            <template #default="{ row }">
              <div class="resume-name-cell">
                <strong>{{ row.title }}</strong>
                <span class="muted-note">
                  {{ row.section_count }} 章节 · {{ row.entry_count }} 条目
                </span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="候选人" width="110">
            <template #default="{ row }">{{ row.candidate_name || '—' }}</template>
          </el-table-column>
          <el-table-column label="目标岗位" min-width="190">
            <template #default="{ row }">
              <span v-if="row.target_announcement_id">
                {{ announcementMap.get(row.target_announcement_id) || '公告已删除' }}
              </span>
              <span v-else class="muted-note">未设置</span>
            </template>
          </el-table-column>
          <el-table-column label="模板" width="112">
            <template #default="{ row }">{{ templateLabel(row.template) }}</template>
          </el-table-column>
          <el-table-column label="版本" width="84">
            <template #default="{ row }">
              <el-tag size="small" effect="plain">v{{ row.content_version }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="更新时间" width="152">
            <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="132" align="right">
            <template #default="{ row }">
              <el-button link type="primary" @click.stop="openResume(row)">打开</el-button>
              <el-button link type="danger" :icon="Delete" @click.stop="handleDelete(row)">
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="total > PAGE_SIZE" class="table-card-foot">
          <el-pagination
            layout="prev, pager, next"
            :current-page="page"
            :page-size="PAGE_SIZE"
            :total="total"
            @current-change="handlePageChange"
          />
        </div>
      </template>
    </section>

    <el-dialog v-model="importOpen" title="导入简历" width="720px">
      <el-tabs v-model="importMode" stretch>
        <el-tab-pane label="粘贴文本" name="text" />
        <el-tab-pane label="上传文件" name="file" />
      </el-tabs>
      <el-form label-position="top" @submit.prevent="submitImport">
        <el-form-item label="简历名称">
          <el-input v-model="importForm.display_name" maxlength="200" placeholder="例如：我的中文简历 2026" />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="目标岗位公告（可选）">
            <el-select
              v-model="importForm.target_announcement_id"
              clearable
              filterable
              placeholder="选择后默认按该公告优化"
            >
              <el-option
                v-for="announcement in announcements"
                :key="announcement.id"
                :label="`${announcement.company.name} · ${announcement.title}`"
                :value="announcement.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="初始模板">
            <ResumeTemplatePicker v-model="importForm.template" />
          </el-form-item>
        </div>
        <el-form-item v-if="importMode === 'text'" label="简历原文">
          <el-input
            v-model="importForm.raw_text"
            type="textarea"
            :rows="10"
            placeholder="建议保留「教育经历」「项目经历」「专业技能」等章节标题……"
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
      </el-form>
      <template #footer>
        <el-button @click="importOpen = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitImport">
          解析成可编辑简历
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="manualOpen" title="新建空白简历" width="560px">
      <p class="panel-note">
        会预置教育经历 / 工作·实习经历 / 项目经历 / 专业技能 / 自我评价五个空章节，可随时增删。
      </p>
      <el-form label-position="top" @submit.prevent="submitManual">
        <el-form-item label="简历名称">
          <el-input v-model="manualForm.title" maxlength="200" placeholder="例如：我的简历 2026" />
        </el-form-item>
        <el-form-item label="目标岗位公告（可选）">
          <el-select
            v-model="manualForm.target_announcement_id"
            clearable
            filterable
            placeholder="选择后默认按该公告优化"
          >
            <el-option
              v-for="announcement in announcements"
              :key="announcement.id"
              :label="`${announcement.company.name} · ${announcement.title}`"
              :value="announcement.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="初始模板">
          <ResumeTemplatePicker v-model="manualForm.template" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="manualOpen = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitManual">
          创建并开始填写
        </el-button>
      </template>
    </el-dialog>
  </main>
</template>
