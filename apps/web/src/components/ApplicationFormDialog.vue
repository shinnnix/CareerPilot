<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { getApiErrorMessage } from '@/api/errors'
import { createApplications } from '@/api/workspace'
import type { JobAnnouncement } from '@/types/workspace'

const props = defineProps<{
  modelValue: boolean
  announcement: JobAnnouncement | null
  presetPositionIds?: string[]
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'created', count: number): void
}>()

const CHANNELS = ['官网', '公众号邮箱', '网申链接', '内推', '招聘平台', '其他']

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const submitting = ref(false)
const selected = ref<string[]>([])

const form = reactive({
  status: 'applied',
  applied_at: '',
  channel: '官网',
  contact_name: '',
  contact_info: '',
  notes: '',
})

const availablePositions = computed(() =>
  (props.announcement?.positions || []).filter((position) => !position.application_id),
)

watch(visible, (open) => {
  if (!open) return
  form.status = 'applied'
  form.applied_at = new Date().toISOString().slice(0, 10)
  form.channel = '官网'
  form.contact_name = ''
  form.contact_info = ''
  form.notes = ''
  const presets = (props.presetPositionIds || []).filter((id) =>
    availablePositions.value.some((position) => position.id === id),
  )
  selected.value = presets.length
    ? presets
    : availablePositions.value.slice(0, 1).map((position) => position.id)
})

async function submit() {
  if (!props.announcement) return
  if (!selected.value.length) {
    ElMessage.warning('请至少选择一个岗位')
    return
  }
  submitting.value = true
  try {
    const result = await createApplications({
      announcement_id: props.announcement.id,
      position_ids: selected.value,
      status: form.status,
      applied_at: form.applied_at ? `${form.applied_at}T00:00:00+00:00` : null,
      channel: form.channel || null,
      contact_name: form.contact_name || null,
      contact_info: form.contact_info || null,
      notes: form.notes || null,
    })
    ElMessage.success(`已创建 ${result.total} 条投递记录`)
    visible.value = false
    emit('created', result.total)
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="创建投递记录" width="620px">
    <p class="panel-note">
      {{ announcement?.company.name }} · {{ announcement?.title }}
    </p>
    <el-form label-position="top" @submit.prevent="submit">
      <el-form-item label="选择岗位（可多选，每个岗位生成一条记录）">
        <el-select v-model="selected" multiple placeholder="选择岗位" class="full-width">
          <el-option
            v-for="position in availablePositions"
            :key="position.id"
            :label="position.title"
            :value="position.id"
          />
        </el-select>
      </el-form-item>
      <div class="form-grid">
        <el-form-item label="状态">
          <el-select v-model="form.status">
            <el-option label="已投递" value="applied" />
            <el-option label="未投递" value="not_applied" />
          </el-select>
        </el-form-item>
        <el-form-item label="投递日期">
          <el-date-picker v-model="form.applied_at" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="渠道">
          <el-select v-model="form.channel" clearable>
            <el-option v-for="item in CHANNELS" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="form.contact_name" maxlength="100" />
        </el-form-item>
        <el-form-item label="联系方式">
          <el-input v-model="form.contact_info" maxlength="200" />
        </el-form-item>
      </div>
      <el-form-item label="备注">
        <el-input v-model="form.notes" type="textarea" :rows="3" maxlength="5000" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>
