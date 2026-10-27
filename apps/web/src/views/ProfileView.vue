<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Download, MagicStick, Plus, Refresh, Upload } from '@element-plus/icons-vue'

import { getResume, listResumes } from '@/api/resumes'
import { useProfileStore } from '@/stores/profile'
import {
  PROFILE_FIELD_LABELS,
  SENSITIVE_PATHS,
  SYNC_CHANNEL_HINTS,
  SYNC_CHANNEL_LABELS,
} from '@/types/profile'
import type {
  ProfileEducation,
  ProfileExperience,
  ProfileProject,
  SyncChannel,
} from '@/types/profile'
import type { ResumeSummary } from '@/types/resumes'

const store = useProfileStore()

const resumePickerOpen = ref(false)
const resumeOptions = ref<ResumeSummary[]>([])
const loadingResumes = ref(false)
const importOpen = ref(false)
const importText = ref('')
const includeSensitive = ref(false)
const syncing = ref(false)

const basic = computed(() => store.profile.basic)
const channel = computed<SyncChannel>(() => store.channel)
const channelLabel = computed(() => SYNC_CHANNEL_LABELS[channel.value])
const channelHint = computed(() => SYNC_CHANNEL_HINTS[channel.value])
const sensitiveSet = new Set<string>(SENSITIVE_PATHS)

const channelType = computed(() => {
  if (channel.value === 'direct') return 'success'
  if (channel.value === 'storage') return 'warning'
  return 'info'
})

function isSensitive(path: string): boolean {
  return sensitiveSet.has(path)
}

function label(path: string): string {
  return PROFILE_FIELD_LABELS[path] ?? path
}

function confirmTag(path: string): string {
  return store.isConfirmed(path) ? '已确认' : '待确认'
}

onMounted(() => {
  store.detectChannel()
})

async function openResumePicker(): Promise<void> {
  resumePickerOpen.value = true
  loadingResumes.value = true
  try {
    const result = await listResumes({ page: 1, page_size: 50 })
    resumeOptions.value = result.items
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    loadingResumes.value = false
  }
}

async function prefillFromResume(resumeId: string): Promise<void> {
  resumePickerOpen.value = false
  try {
    const resume = await getResume(resumeId)
    const filled = store.prefillFromResume(resume)
    ElMessage.success(filled ? `已从简历预填 ${filled} 个字段` : '简历里的基础字段都已存在，未覆盖')
  } catch (error) {
    ElMessage.error((error as Error).message)
  }
}

async function runSync(): Promise<void> {
  syncing.value = true
  try {
    const used = await store.sync(includeSensitive.value)
    if (used === 'json') {
      ElMessage.warning(store.syncMessage)
      return
    }
    ElMessage.success(store.syncMessage)
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    syncing.value = false
  }
}

function downloadExport(): void {
  const text = store.exportJson(includeSensitive.value)
  const blob = new Blob([text], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `careerpilot-profile-${new Date().toISOString().slice(0, 10)}.json`
  anchor.click()
  URL.revokeObjectURL(url)
  if (!includeSensitive.value) {
    ElMessage.info('导出文件已剔除身份证号与学号')
  }
}

function openImport(): void {
  importText.value = ''
  importOpen.value = true
}

function submitImport(): void {
  const result = store.importJson(importText.value)
  if (!result.ok) {
    ElMessage.error(result.error ?? '导入失败')
    return
  }
  importOpen.value = false
  ElMessage.success('已导入本地个人信息')
}

async function clearAll(): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '将清空浏览器中的个人信息（不可恢复，后端从未存过这些数据）。确定继续？',
      '清空个人信息',
      { type: 'warning', confirmButtonText: '清空', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  store.clear()
  ElMessage.success('已清空')
}

function addEducation(): void {
  const row: ProfileEducation = {
    id: crypto.randomUUID(),
    school: '',
    major: '',
    degree: '',
    startDate: '',
    endDate: '',
    gpa: '',
  }
  store.setEducation([...store.profile.education, row])
}

function addExperience(): void {
  const row: ProfileExperience = {
    id: crypto.randomUUID(),
    company: '',
    title: '',
    startDate: '',
    endDate: '',
    description: '',
  }
  store.setExperience([...store.profile.experience, row])
}

function addProject(): void {
  const row: ProfileProject = {
    id: crypto.randomUUID(),
    name: '',
    role: '',
    startDate: '',
    endDate: '',
    description: '',
    link: '',
  }
  store.setProjects([...store.profile.projects, row])
}

function removeRow(kind: 'education' | 'experience' | 'projects', id: string): void {
  if (kind === 'education') {
    store.setEducation(store.profile.education.filter((row) => row.id !== id))
    return
  }
  if (kind === 'experience') {
    store.setExperience(store.profile.experience.filter((row) => row.id !== id))
    return
  }
  store.setProjects(store.profile.projects.filter((row) => row.id !== id))
}
</script>

<template>
  <main class="page">
    <header class="page-head">
      <div>
        <p class="eyebrow">更多工具</p>
        <h1>网申个人信息</h1>
        <p class="page-desc">
          网申表格反复填的那些字段，在这里维护一次。数据只存在这台电脑的浏览器里，
          后端不建表、不接收存储请求，只在自动填写时按次使用。
        </p>
      </div>
      <div class="page-head-actions">
        <el-button :icon="MagicStick" @click="openResumePicker">从简历预填</el-button>
        <el-button :icon="Download" @click="downloadExport">导出 JSON</el-button>
        <el-button :icon="Upload" @click="openImport">导入 JSON</el-button>
        <el-button type="danger" plain :icon="Delete" @click="clearAll">清空</el-button>
      </div>
    </header>

    <section class="surface profile-sync">
      <div class="profile-sync-head">
        <div>
          <p class="eyebrow">同步到插件</p>
          <h2>当前生效通道：{{ channelLabel }}</h2>
          <p class="muted-note">{{ channelHint }}</p>
        </div>
        <div class="profile-sync-actions">
          <el-input
            v-model="store.extensionId"
            class="profile-ext-id"
            placeholder="扩展 ID（通道①需要）"
            clearable
            @change="store.setExtensionId($event)"
          />
          <el-button
            type="primary"
            :loading="syncing"
            :disabled="!store.isConfigured"
            @click="runSync"
          >
            同步到插件
          </el-button>
        </div>
      </div>
      <el-alert
        :type="channelType"
        :closable="false"
        show-icon
        :title="`通道降级顺序：① 直连扩展 → ② 读取页面存储 → ③ 导出 JSON 粘贴（当前：${channelLabel}）`"
      >
        <p v-if="store.lastSyncedAt" class="muted-note">
          上次同步：{{ new Date(store.lastSyncedAt).toLocaleString() }}
        </p>
        <p v-if="store.syncMessage" class="muted-note">{{ store.syncMessage }}</p>
      </el-alert>
      <el-checkbox v-model="includeSensitive" class="profile-sensitive-toggle">
        同步/导出时包含敏感字段（身份证号、学号）
      </el-checkbox>
      <p class="muted-note">
        默认剔除敏感字段；开启后仅在本机浏览器内传递，不经过后端。
      </p>
    </section>

    <section class="surface profile-card">
      <div class="table-card-head">
        <h2>基本信息</h2>
        <span class="muted-note">已填写 {{ store.filledCount }} 项</span>
      </div>
      <el-form label-position="top" class="form-grid profile-form">
        <el-form-item
          v-for="path in [
            'basic.name',
            'basic.gender',
            'basic.birthday',
            'basic.phone',
            'basic.email',
            'basic.wechat',
            'basic.city',
            'basic.hometown',
            'basic.politicalStatus',
          ]"
          :key="path"
        >
          <template #label>
            <span class="profile-label">
              {{ label(path) }}
              <el-tag size="small" effect="plain" :type="store.isConfirmed(path) ? 'success' : 'info'">
                {{ confirmTag(path) }}
              </el-tag>
            </span>
          </template>
          <el-input
            :model-value="(basic as unknown as Record<string, string>)[path.replace('basic.', '')]"
            :placeholder="`填写${label(path)}`"
            @update:model-value="
              store.updateBasic({ [path.replace('basic.', '')]: $event } as never)
            "
          />
        </el-form-item>
      </el-form>
      <div class="profile-sensitive">
        <p class="muted-note">
          敏感字段：只存本地，默认不填充，需在插件里显式授权后才会使用。
        </p>
        <el-form label-position="top" class="form-grid profile-form">
          <el-form-item v-for="path in SENSITIVE_PATHS" :key="path">
            <template #label>
              <span class="profile-label">
                {{ label(path) }}
                <el-tag size="small" type="warning" effect="plain">敏感</el-tag>
              </span>
            </template>
            <el-input
              :model-value="(basic as unknown as Record<string, string>)[path.replace('basic.', '')]"
              show-password
              :placeholder="isSensitive(path) ? '默认不传输' : ''"
              @update:model-value="
                store.updateBasic({ [path.replace('basic.', '')]: $event } as never, false)
              "
            />
          </el-form-item>
        </el-form>
      </div>
    </section>

    <section class="surface profile-card">
      <div class="table-card-head">
        <h2>教育经历</h2>
        <el-button size="small" :icon="Plus" @click="addEducation">添加</el-button>
      </div>
      <p v-if="!store.profile.education.length" class="muted-note profile-empty">
        还没有教育经历。可以「从简历预填」，或手动添加。
      </p>
      <div v-for="row in store.profile.education" :key="row.id" class="profile-row">
        <el-input v-model="row.school" placeholder="学校" />
        <el-input v-model="row.major" placeholder="专业" />
        <el-input v-model="row.degree" placeholder="学历" />
        <el-input v-model="row.startDate" placeholder="开始（2022-09）" />
        <el-input v-model="row.endDate" placeholder="结束（2026-06）" />
        <el-input v-model="row.gpa" placeholder="GPA" />
        <el-button text type="danger" :icon="Delete" @click="removeRow('education', row.id)" />
      </div>
    </section>

    <section class="surface profile-card">
      <div class="table-card-head">
        <h2>实习 / 工作经历</h2>
        <el-button size="small" :icon="Plus" @click="addExperience">添加</el-button>
      </div>
      <p v-if="!store.profile.experience.length" class="muted-note profile-empty">
        网申常问「最近一段实习」，写在这里就不用每次翻简历。
      </p>
      <div v-for="row in store.profile.experience" :key="row.id" class="profile-row">
        <el-input v-model="row.company" placeholder="公司" />
        <el-input v-model="row.title" placeholder="职位" />
        <el-input v-model="row.startDate" placeholder="开始" />
        <el-input v-model="row.endDate" placeholder="结束" />
        <el-input v-model="row.description" placeholder="一句话职责" />
        <el-button text type="danger" :icon="Delete" @click="removeRow('experience', row.id)" />
      </div>
    </section>

    <section class="surface profile-card">
      <div class="table-card-head">
        <h2>项目经历</h2>
        <el-button size="small" :icon="Plus" @click="addProject">添加</el-button>
      </div>
      <p v-if="!store.profile.projects.length" class="muted-note profile-empty">暂无项目。</p>
      <div v-for="row in store.profile.projects" :key="row.id" class="profile-row">
        <el-input v-model="row.name" placeholder="项目名" />
        <el-input v-model="row.role" placeholder="角色" />
        <el-input v-model="row.startDate" placeholder="开始" />
        <el-input v-model="row.endDate" placeholder="结束" />
        <el-input v-model="row.link" placeholder="链接" />
        <el-button text type="danger" :icon="Delete" @click="removeRow('projects', row.id)" />
      </div>
    </section>

    <section class="surface profile-card">
      <div class="table-card-head">
        <h2>技能与证书</h2>
      </div>
      <el-form label-position="top" class="profile-form">
        <el-form-item label="技能（回车添加）">
          <el-select
            :model-value="store.profile.skills.skills"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="Python、FastAPI、SQL"
            style="width: 100%"
            @update:model-value="store.updateSkills({ skills: $event as string[] })"
          />
        </el-form-item>
        <el-form-item label="证书">
          <el-select
            :model-value="store.profile.skills.certificates"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="CET-6、软考中级"
            style="width: 100%"
            @update:model-value="store.updateSkills({ certificates: $event as string[] })"
          />
        </el-form-item>
        <el-form-item label="语言">
          <el-select
            :model-value="store.profile.skills.languages"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="中文、英语"
            style="width: 100%"
            @update:model-value="store.updateSkills({ languages: $event as string[] })"
          />
        </el-form-item>
      </el-form>
    </section>

    <section class="surface profile-card">
      <div class="table-card-head">
        <h2>求职偏好</h2>
      </div>
      <el-form label-position="top" class="form-grid profile-form">
        <el-form-item label="期望城市">
          <el-select
            :model-value="store.profile.preferences.cities"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="上海、杭州"
            style="width: 100%"
            @update:model-value="store.updatePreferences({ cities: $event as string[] })"
          />
        </el-form-item>
        <el-form-item label="期望岗位">
          <el-select
            :model-value="store.profile.preferences.roles"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="后端开发实习"
            style="width: 100%"
            @update:model-value="store.updatePreferences({ roles: $event as string[] })"
          />
        </el-form-item>
        <el-form-item label="可到岗时间">
          <el-input
            :model-value="store.profile.preferences.availableFrom"
            placeholder="随时 / 2026-07"
            @update:model-value="store.updatePreferences({ availableFrom: $event })"
          />
        </el-form-item>
        <el-form-item label="每周可实习天数">
          <el-input
            :model-value="store.profile.preferences.daysPerWeek"
            placeholder="5"
            @update:model-value="store.updatePreferences({ daysPerWeek: $event })"
          />
        </el-form-item>
        <el-form-item label="可实习月数">
          <el-input
            :model-value="store.profile.preferences.monthsAvailable"
            placeholder="6"
            @update:model-value="store.updatePreferences({ monthsAvailable: $event })"
          />
        </el-form-item>
        <el-form-item label="期望薪资">
          <el-input
            :model-value="store.profile.preferences.salaryExpectation"
            placeholder="200/天"
            @update:model-value="store.updatePreferences({ salaryExpectation: $event })"
          />
        </el-form-item>
      </el-form>
    </section>

    <section class="surface profile-card">
      <div class="table-card-head">
        <h2>链接</h2>
      </div>
      <el-form label-position="top" class="form-grid profile-form">
        <el-form-item
          v-for="key in ['github', 'portfolio', 'blog', 'linkedin']"
          :key="key"
          :label="key"
        >
          <el-input
            :model-value="(store.profile.links as unknown as Record<string, string>)[key]"
            :placeholder="`https://${key}.com/...`"
            @update:model-value="store.updateLinks({ [key]: $event } as never)"
          />
        </el-form-item>
      </el-form>
    </section>

    <el-dialog v-model="resumePickerOpen" title="从简历预填" width="560px">
      <p class="muted-note">只填充当前为空的字段，已填写的内容不会被覆盖。</p>
      <el-skeleton v-if="loadingResumes" :rows="4" animated />
      <el-empty v-else-if="!resumeOptions.length" description="还没有简历，先去「我的简历」创建" />
      <ul v-else class="resume-picker-list">
        <li v-for="item in resumeOptions" :key="item.id">
          <button type="button" class="resume-picker-row" @click="prefillFromResume(item.id)">
            <span>
              <strong>{{ item.title }}</strong>
              <small class="muted-note">{{ item.section_count }} 个区块</small>
            </span>
            <el-icon><Refresh /></el-icon>
          </button>
        </li>
      </ul>
    </el-dialog>

    <el-dialog v-model="importOpen" title="导入 JSON" width="560px">
      <p class="muted-note">
        粘贴导出的个人信息文件，或插件里复制出来的 JSON。会整体覆盖当前内容。
      </p>
      <el-input v-model="importText" type="textarea" :rows="12" placeholder='{"schemaVersion":1,...}' />
      <template #footer>
        <el-button @click="importOpen = false">取消</el-button>
        <el-button type="primary" :disabled="!importText.trim()" @click="submitImport">
          导入
        </el-button>
      </template>
    </el-dialog>
  </main>
</template>
