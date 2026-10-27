<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Connection, Refresh, Search } from '@element-plus/icons-vue'

import { getApiErrorMessage } from '@/api/errors'
import { indexKnowledgeBase, searchKnowledgeBase } from '@/api/retrieval'
import type { RetrievalMode, SearchResponse } from '@/types/retrieval'

const query = ref('')
const mode = ref<RetrievalMode>('hybrid')
const loading = ref(false)
const indexing = ref(false)
const result = ref<SearchResponse | null>(null)

async function search() {
  if (!query.value.trim()) return
  loading.value = true
  try {
    result.value = await searchKnowledgeBase({
      query: query.value,
      mode: mode.value,
      top_k: 8,
      expand_parent: true,
    })
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function indexAll() {
  indexing.value = true
  try {
    const response = await indexKnowledgeBase({ force: false })
    ElMessage.success(`完成 ${response.indexed_chunks} 个 Chunk 的向量化`)
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    indexing.value = false
  }
}

function score(value: number | null) {
  return value === null ? '—' : value.toFixed(4)
}
</script>

<template>
  <main class="page">
    <header class="page-head">
      <div>
        <p class="eyebrow">更多工具</p>
        <h1>证据检索</h1>
        <p class="page-desc">
          从自己的资料里找可引用的证据，用来解释匹配分、准备面试回答。
          每条结果都带出处与父 Chunk 上下文，方便直接引用。
        </p>
      </div>
      <div class="page-head-actions">
        <el-button :icon="Refresh" :loading="indexing" @click="indexAll">更新向量索引</el-button>
      </div>
    </header>

    <section class="surface retrieval-toolbar">
      <el-input
        v-model="query"
        :prefix-icon="Search"
        size="large"
        placeholder="例如：用 FastAPI 做过什么项目"
        @keyup.enter="search"
      />
      <el-select v-model="mode" size="large">
        <el-option label="关键词" value="keyword" />
        <el-option label="语义" value="dense" />
        <el-option label="混合（默认）" value="hybrid" />
        <el-option label="混合 + 重排" value="rerank" />
      </el-select>
      <el-button type="primary" size="large" :icon="Connection" :loading="loading" @click="search">
        检索
      </el-button>
    </section>

    <section v-if="result" class="retrieval-results">
      <div class="section-heading">
        <div>
          <p class="eyebrow">结果</p>
          <h2>{{ result.items.length }} 条证据</h2>
        </div>
        <span>{{ result.embedding_model }} · {{ result.latency_ms }} ms</span>
      </div>
      <el-empty v-if="!result.items.length" description="没有找到相关证据" />
      <article v-for="(hit, index) in result.items" :key="hit.chunk_id" class="surface retrieval-hit">
        <header>
          <strong>#{{ index + 1 }} {{ hit.document_name }}</strong>
          <span>{{ hit.section_path.join(' / ') }}</span>
        </header>
        <p>{{ hit.expanded_content || hit.content }}</p>
        <footer>
          <span>关键词 {{ score(hit.keyword_score) }}</span>
          <span>语义 {{ score(hit.dense_score) }}</span>
          <span>融合 {{ score(hit.fusion_score) }}</span>
          <span>重排 {{ score(hit.rerank_score) }}</span>
        </footer>
      </article>
    </section>
  </main>
</template>
