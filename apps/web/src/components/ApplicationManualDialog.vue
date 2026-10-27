<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { getApiErrorCode, getApiErrorMessage } from '@/api/errors'
import { createApplications } from '@/api/workspace'
import { APPLICATION_CHANNELS, APPLICATION_STATUS_LABELS } from '@/types/applications'
import { today, toIsoDate } from '@/utils/applicationStatus'

const props = defineProps<{ modelValue: boolean }>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'created', count: number): void
}>()

/** Manual entry defaults to 已投递; drafts are allowed via 未投递 (plan §3.5). */
const CREATE_STATUSES = ['not_applied', 'applied', 'written_test', 'interview_done', 'offer', 'rejected', 'withdrawn']

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const submitting = ref(false)
const form = reactive({
  company_name: '',
  position_title: '',
  status: 'applied',
  applied_at: '',
  follow_up_at: '',
  channel: '官网',
  contact_name: '',
  contact_info: '',
  link: '',
  notes: '',
})

watch(visible, (open) => {
  if (!open) return
  form.company_name = ''
  form.position_title = ''
  form.status = 'applied'
  form.applied_at = today()
  form.follow_up_at = ''
  form.channel = '官网'
  form.contact_name = ''
  form.contact_info = ''
  form.link = ''
  form.notes = ''
})

function validate(): string | null {
  if (!form.company_name.trim()) return '请填写公司名称'
  if (!form.position_title.trim()) return '请填写岗位名称'
  if (form.applied_at && form.follow_up_at && form.follow_up_at < form.applied_at) {
    return '跟进日期不能早于投递日期'
  }
  return null
}

function payload(allowDuplicate: boolean) {
  return {
    company_name: form.company_name.trim(),
    position_title: form.position_title.trim(),
    status: form.status,
    applied_at: toIsoDate(form.applied_at),
    follow_up_at: toIsoDate(form.follow_up_at),
    channel: form.channel || null,
    contact_name: form.contact_name.trim() || null,
    contact_info: form.contact_info.trim() || null,
    link: form.link.trim() || null,
    notes: form.notes.trim() || null,
    allow_duplicate: allowDuplicate,
  }
}

async function submit() {
  const problem = validate()
  if (problem) {
    ElMessage.warning(problem)
    return
  }
  submitting.value = true
  try {
    const result = await createApplications(payload(false))
    ElMessage.success(`已新增 ${result.total} 条投递记录`)
    visible.value = false
    emit('created', result.total)
  } catch (error) {
    if (getApiErrorCode(error) === 'APPLICATION_DUPLICATE_HINT') {
      const confirmed = await ElMessageBox.confirm(
        '已存在公司、岗位与投递日期都相同的记录，仍然再建一条？',
        '可能重复',
        { confirmButtonText: '仍然新增', cancelButtonText: '取消', type: 'warning' },
      )
        .then(() => true)
        .catch(() => false)
      if (confirmed) {
        try {
          const forced = await createApplications(payload(true))
          ElMessage.success(`已新增 ${forced.total} 条投递记录`)
          visible.value = false
          emit('created', forced.total)
        } catch (retryError) {
          ElMessage.error(getApiErrorMessage(retryError))
        }
      }
    } else {
      ElMessage.error(getApiErrorMessage(error))
    }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="手动新增投递" width="640px">
    <el-form label-position="top" @submit.prevent="submit">
      <div class="form-grid">
        <el-form-item label="公司名称" required>
          <el-input v-model="form.company_name" maxlength="200" placeholder="例如：星河智能" />
        </el-form-item>
        <el-form-item label="岗位名称" required>
          <el-input v-model="form.position_title" maxlength="200" placeholder="例如：后端开发工程师" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status">
            <el-option
              v-for="status in CREATE_STATUSES"
              :key="status"
              :label="APPLICATION_STATUS_LABELS[status as keyof typeof APPLICATION_STATUS_LABELS]"
              :value="status"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="投递日期">
          <el-date-picker v-model="form.applied_at" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="跟进日期">
          <el-date-picker v-model="form.follow_up_at" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="渠道">
          <el-select v-model="form.channel" clearable>
            <el-option v-for="item in APPLICATION_CHANNELS" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="form.contact_name" maxlength="100" />
        </el-form-item>
        <el-form-item label="联系方式">
          <el-input v-model="form.contact_info" maxlength="200" placeholder="邮箱 / 微信 / 电话" />
        </el-form-item>
      </div>
      <el-form-item label="公告 / 职位链接">
        <el-input v-model="form.link" maxlength="1000" placeholder="https://" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.notes" type="textarea" :rows="3" maxlength="5000" show-word-limit />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>
