<script setup lang="ts">
import { Search } from '@element-plus/icons-vue'
import { onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import JobCard from '@/components/JobCard.vue'
import { useJobs } from '@/composables/useJobs'
import { usePreferencesStore } from '@/stores/preferences'

const route = useRoute()
const router = useRouter()
const preferences = usePreferencesStore()
const { jobs, loading, errorMessage, total, query, search } = useJobs()

query.keyword = typeof route.query.keyword === 'string' ? route.query.keyword : ''
query.city = typeof route.query.city === 'string' ? route.query.city : ''
query.page = Number(route.query.page) || 1
query.page_size = preferences.pageSize

async function submitSearch() {
  query.page = 1
  await syncRouteAndSearch()
}

async function syncRouteAndSearch() {
  await router.replace({
    query: {
      ...(query.keyword ? { keyword: query.keyword } : {}),
      ...(query.city ? { city: query.city } : {}),
      ...(query.page && query.page > 1 ? { page: String(query.page) } : {}),
    },
  })
  await search()
}

watch(
  () => query.page,
  async () => {
    await syncRouteAndSearch()
  },
)

onMounted(search)
</script>

<template>
  <main class="page">
    <section class="hero">
      <div>
        <p class="eyebrow">CAREERPILOT · WEEK 6</p>
        <h1>从发现 AI 实习<br />到准备申请的工作台</h1>
        <p class="hero-copy">
          用私人知识库、混合检索、可解释匹配和可恢复 Agent 管理每一次求职决策。
        </p>
      </div>
      <div class="hero-stat">
        <strong>{{ total }}</strong>
        <span>个职位记录</span>
      </div>
    </section>

    <section class="search-panel">
      <el-input
        v-model="query.keyword"
        size="large"
        clearable
        placeholder="搜索职位、公司或 JD，例如 RAG"
        :prefix-icon="Search"
        @keyup.enter="submitSearch"
      />
      <el-input
        v-model="query.city"
        size="large"
        clearable
        placeholder="城市，例如 上海"
        @keyup.enter="submitSearch"
      />
      <el-button type="primary" size="large" @click="submitSearch">搜索职位</el-button>
    </section>

    <section class="section-heading">
      <div>
        <p class="eyebrow">JOB LIBRARY</p>
        <h2>职位列表</h2>
      </div>
      <span v-if="!loading">共 {{ total }} 条结果</span>
    </section>

    <div v-if="loading" class="job-grid" aria-label="正在加载">
      <el-skeleton v-for="index in 6" :key="index" :rows="5" animated class="job-card" />
    </div>

    <el-alert
      v-else-if="errorMessage"
      :title="errorMessage"
      type="error"
      show-icon
      :closable="false"
    >
      <template #default>
        <el-button class="retry-button" @click="search">重新加载</el-button>
      </template>
    </el-alert>

    <el-empty
      v-else-if="jobs.length === 0"
      description="还没有符合条件的职位"
    >
      <RouterLink to="/jobs/new">
        <el-button type="primary">添加第一个职位</el-button>
      </RouterLink>
    </el-empty>

    <template v-else>
      <div class="job-grid">
        <JobCard v-for="job in jobs" :key="job.id" :job="job" />
      </div>
      <el-pagination
        v-if="total > (query.page_size || 9)"
        v-model:current-page="query.page"
        :page-size="query.page_size"
        :total="total"
        layout="prev, pager, next"
        class="pagination"
      />
    </template>
  </main>
</template>
