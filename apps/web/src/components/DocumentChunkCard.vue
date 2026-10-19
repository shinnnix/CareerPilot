<script setup lang="ts">
import type { DocumentChunk } from '@/types/documents'

defineProps<{
  chunk: DocumentChunk
}>()

const chunkTypeLabels: Record<string, string> = {
  responsibility: '岗位职责',
  requirement: '任职要求',
  preferred_requirement: '加分项',
  experience: '经历',
  education: '教育',
  skill: '技能',
  paragraph: '正文',
}
</script>

<template>
  <article class="chunk-card">
    <div class="chunk-card__header">
      <div>
        <span class="chunk-index">#{{ chunk.position + 1 }}</span>
        <strong>{{ chunk.section_path.join(' / ') }}</strong>
      </div>
      <el-tag size="small" effect="plain">
        {{ chunkTypeLabels[chunk.chunk_type] || chunk.chunk_type }}
      </el-tag>
    </div>
    <p>{{ chunk.content }}</p>
    <footer>
      <span>{{ chunk.char_count }} 字符</span>
      <span>约 {{ chunk.estimated_token_count }} tokens</span>
      <span>{{ chunk.index_version }}</span>
    </footer>
  </article>
</template>

