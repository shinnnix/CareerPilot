<script setup lang="ts">
import { reactive, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ref } from 'vue'

import type { Job, JobInput } from '@/types/jobs'

const props = defineProps<{
  job?: Job
  submitting?: boolean
  submitLabel?: string
}>()

const emit = defineEmits<{
  submit: [payload: JobInput]
  cancel: []
}>()

const formRef = ref<FormInstance>()
const requiredSkillsText = ref('')
const preferredSkillsText = ref('')

const emptyForm = (): JobInput => ({
  title: '',
  company_name: '',
  city: null,
  employment_type: 'internship',
  remote_type: 'onsite',
  salary_min: null,
  salary_max: null,
  internship_days_per_week: null,
  internship_months: null,
  required_skills: [],
  preferred_skills: [],
  source_url: null,
  raw_text: '',
  status: 'active',
})

const form = reactive<JobInput>(emptyForm())

watch(
  () => props.job,
  (job) => {
    Object.assign(form, job ? {
      title: job.title,
      company_name: job.company_name,
      city: job.city,
      employment_type: job.employment_type,
      remote_type: job.remote_type,
      salary_min: job.salary_min,
      salary_max: job.salary_max,
      internship_days_per_week: job.internship_days_per_week,
      internship_months: job.internship_months,
      required_skills: [...job.required_skills],
      preferred_skills: [...job.preferred_skills],
      source_url: job.source_url,
      raw_text: job.raw_text,
      status: job.status,
    } : emptyForm())
    requiredSkillsText.value = job?.required_skills.join(', ') || ''
    preferredSkillsText.value = job?.preferred_skills.join(', ') || ''
  },
  { immediate: true },
)

const rules: FormRules<JobInput> = {
  title: [
    { required: true, message: '请输入职位名称', trigger: 'blur' },
    { min: 2, max: 100, message: '长度为 2–100 个字符', trigger: 'blur' },
  ],
  company_name: [{ required: true, message: '请输入公司名称', trigger: 'blur' }],
  raw_text: [
    { required: true, message: '请输入职位描述', trigger: 'blur' },
    { min: 20, message: '职位描述至少需要 20 个字符', trigger: 'blur' },
  ],
}

function splitSkills(value: string): string[] {
  return [...new Set(value.split(/[,，\n]/).map((item) => item.trim()).filter(Boolean))]
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  form.required_skills = splitSkills(requiredSkillsText.value)
  form.preferred_skills = splitSkills(preferredSkillsText.value)
  emit('submit', {
    ...form,
    city: form.city || null,
    source_url: form.source_url || null,
  })
}
</script>

<template>
  <el-form
    ref="formRef"
    :model="form"
    :rules="rules"
    label-position="top"
    class="job-form"
    @submit.prevent="handleSubmit"
  >
    <div class="form-grid">
      <el-form-item label="职位名称" prop="title">
        <el-input v-model="form.title" placeholder="例如：AI 应用开发实习生" />
      </el-form-item>
      <el-form-item label="公司名称" prop="company_name">
        <el-input v-model="form.company_name" placeholder="例如：示例科技" />
      </el-form-item>
      <el-form-item label="城市">
        <el-input v-model="form.city" placeholder="上海" />
      </el-form-item>
      <el-form-item label="办公方式">
        <el-select v-model="form.remote_type">
          <el-option label="现场" value="onsite" />
          <el-option label="混合" value="hybrid" />
          <el-option label="远程" value="remote" />
        </el-select>
      </el-form-item>
      <el-form-item label="每周实习天数">
        <el-input-number v-model="form.internship_days_per_week" :min="1" :max="7" />
      </el-form-item>
      <el-form-item label="实习月数">
        <el-input-number v-model="form.internship_months" :min="1" :max="36" />
      </el-form-item>
      <el-form-item label="最低日薪/薪资">
        <el-input v-model="form.salary_min" type="number" min="0" placeholder="200" />
      </el-form-item>
      <el-form-item label="最高日薪/薪资">
        <el-input v-model="form.salary_max" type="number" min="0" placeholder="300" />
      </el-form-item>
    </div>
    <el-form-item label="必须技能（逗号分隔）">
      <el-input v-model="requiredSkillsText" placeholder="Python, FastAPI, RAG" />
    </el-form-item>
    <el-form-item label="加分技能（逗号分隔）">
      <el-input v-model="preferredSkillsText" placeholder="Vue 3, LangChain" />
    </el-form-item>
    <el-form-item label="来源链接">
      <el-input v-model="form.source_url" placeholder="https://example.com/job/123" />
    </el-form-item>
    <el-form-item label="职位描述" prop="raw_text">
      <el-input
        v-model="form.raw_text"
        type="textarea"
        :rows="9"
        placeholder="粘贴完整 JD；第一周先保存原文，后续再增加结构化解析与 RAG 索引。"
      />
    </el-form-item>
    <el-form-item label="状态">
      <el-radio-group v-model="form.status">
        <el-radio-button value="active">招聘中</el-radio-button>
        <el-radio-button value="archived">已归档</el-radio-button>
      </el-radio-group>
    </el-form-item>
    <div class="form-actions">
      <el-button @click="emit('cancel')">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        {{ submitLabel || '保存职位' }}
      </el-button>
    </div>
  </el-form>
</template>

