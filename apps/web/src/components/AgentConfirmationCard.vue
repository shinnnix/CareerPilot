<script setup lang="ts">
defineProps<{ toolName: string; loading?: boolean }>()
defineEmits<{ approve: []; reject: [] }>()
</script>

<template>
  <div class="confirmation-card">
    <p>即将执行写操作：<strong>{{ toolName }}</strong></p>
    <el-button type="primary" :loading="loading" @click="$emit('approve')">确认执行</el-button>
    <el-button @click="$emit('reject')">拒绝</el-button>
  </div>
</template>
