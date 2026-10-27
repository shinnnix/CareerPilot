<script setup lang="ts">
import { computed } from 'vue'

import type { JobColumnOption } from '@/types/workspace'

const props = defineProps<{
  columns: JobColumnOption[]
  visible: string[]
}>()

const emit = defineEmits<{
  (event: 'update:visible', value: string[]): void
}>()

const selected = computed({
  get: () => props.visible,
  set: (value: string[]) => {
    if (!value.length) return
    emit('update:visible', value)
  },
})
</script>

<template>
  <el-popover placement="bottom-end" :width="260" trigger="click" popper-class="column-popover">
    <template #reference>
      <button type="button" class="column-settings-trigger">
        列设置 <strong>{{ visible.length }}/{{ columns.length }}</strong>
      </button>
    </template>
    <p class="column-settings-hint">勾选即生效，至少保留 1 列</p>
    <el-checkbox-group v-model="selected" class="column-settings-list">
      <el-checkbox
        v-for="column in columns"
        :key="column.key"
        :value="column.key"
        :disabled="visible.length === 1 && visible.includes(column.key)"
      >
        {{ column.label }}
      </el-checkbox>
    </el-checkbox-group>
  </el-popover>
</template>
