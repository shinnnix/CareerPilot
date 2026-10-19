<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  breakdown: Record<string, number>
}>()

const labels: Record<string, string> = {
  required_skill_coverage: '必备技能',
  preferred_skill_coverage: '加分技能',
  experience_semantic_score: '经历语义',
  project_domain_score: '项目领域',
  preference_score: '地点偏好',
  freshness_score: '岗位新鲜度',
}

const rows = computed(() =>
  Object.entries(props.breakdown).map(([key, value]) => ({
    key,
    label: labels[key] || key,
    value: Math.round(value * 100),
  })),
)
</script>

<template>
  <div>
    <div v-for="row in rows" :key="row.key" class="score-row" :data-score-key="row.key">
      <span>{{ row.label }}</span>
      <el-progress :percentage="row.value" :stroke-width="10" />
    </div>
  </div>
</template>
