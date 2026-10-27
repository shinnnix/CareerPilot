<script setup lang="ts">
import { computed } from 'vue'
import { Search, Setting } from '@element-plus/icons-vue'

import type { FacetOption, JobFacets, JobFilters } from '@/types/workspace'

const props = defineProps<{
  modelValue: JobFilters
  facets: JobFacets
  advancedOpen: boolean
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: JobFilters): void
  (event: 'update:advancedOpen', value: boolean): void
  (event: 'search'): void
  (event: 'reset'): void
}>()

function patch(changes: Partial<JobFilters>) {
  emit('update:modelValue', { ...props.modelValue, ...changes })
}

const keyword = computed({
  get: () => props.modelValue.keyword,
  set: (value: string) => patch({ keyword: value }),
})
const company = computed({
  get: () => props.modelValue.company,
  set: (value: string) => patch({ company: value }),
})
const status = computed({
  get: () => props.modelValue.status,
  set: (value: string) => patch({ status: value ?? '' }),
})
const companyType = computed({
  get: () => props.modelValue.company_type,
  set: (value: string) => patch({ company_type: value ?? '' }),
})
const recruitmentType = computed({
  get: () => props.modelValue.recruitment_type,
  set: (value: string) => patch({ recruitment_type: value ?? '' }),
})
const targetCohort = computed({
  get: () => props.modelValue.target_cohort,
  set: (value: string) => patch({ target_cohort: value ?? '' }),
})
const location = computed({
  get: () => props.modelValue.location,
  set: (value: string) => patch({ location: value ?? '' }),
})
const jobCategory = computed({
  get: () => props.modelValue.job_category,
  set: (value: string) => patch({ job_category: value ?? '' }),
})

const advancedActive = computed(
  () =>
    Boolean(props.modelValue.company_type) ||
    Boolean(props.modelValue.recruitment_type) ||
    Boolean(props.modelValue.target_cohort) ||
    Boolean(props.modelValue.location) ||
    Boolean(props.modelValue.job_category),
)

function options(source: FacetOption[]): FacetOption[] {
  return source.filter((item) => item.value)
}
</script>

<template>
  <section class="surface filter-card">
    <div class="filter-row">
      <el-input
        v-model="keyword"
        class="filter-input"
        clearable
        placeholder="岗位搜索：职位名称、公司或公告正文"
        :prefix-icon="Search"
        @keyup.enter="emit('search')"
      />
      <el-input
        v-model="company"
        class="filter-input filter-input--short"
        clearable
        placeholder="公司名称"
        @keyup.enter="emit('search')"
      />
      <el-select v-model="status" class="filter-select" placeholder="状态筛选" clearable>
        <el-option label="全部状态" value="" />
        <el-option
          v-for="item in facets.statuses"
          :key="item.value"
          :label="`${item.label}（${item.count}）`"
          :value="item.value"
        />
      </el-select>
      <div class="filter-actions">
        <el-button type="primary" :icon="Search" @click="emit('search')">搜索</el-button>
        <el-button @click="emit('reset')">重置</el-button>
        <el-button
          text
          :icon="Setting"
          :class="{ 'is-active': advancedOpen || advancedActive }"
          @click="emit('update:advancedOpen', !advancedOpen)"
        >
          高级筛选
        </el-button>
      </div>
    </div>

    <div v-show="advancedOpen" class="filter-row filter-row--advanced">
      <el-select v-model="companyType" class="filter-select" placeholder="公司类型" clearable>
        <el-option label="全部公司类型" value="" />
        <el-option
          v-for="item in options(facets.company_types)"
          :key="item.value"
          :label="`${item.value}（${item.count}）`"
          :value="item.value"
        />
      </el-select>
      <el-select
        v-model="recruitmentType"
        class="filter-select"
        placeholder="招聘类型"
        clearable
      >
        <el-option label="全部招聘类型" value="" />
        <el-option
          v-for="item in options(facets.recruitment_types)"
          :key="item.value"
          :label="`${item.value}（${item.count}）`"
          :value="item.value"
        />
      </el-select>
      <el-select v-model="targetCohort" class="filter-select" placeholder="招聘对象" clearable>
        <el-option label="全部招聘对象" value="" />
        <el-option
          v-for="item in options(facets.target_cohorts)"
          :key="item.value"
          :label="`${item.value}（${item.count}）`"
          :value="item.value"
        />
      </el-select>
      <el-select v-model="location" class="filter-select" placeholder="工作地点" clearable filterable>
        <el-option label="全部工作地点" value="" />
        <el-option
          v-for="item in options(facets.locations)"
          :key="item.value"
          :label="`${item.value}（${item.count}）`"
          :value="item.value"
        />
      </el-select>
      <el-select
        v-model="jobCategory"
        class="filter-select"
        placeholder="岗位类别"
        clearable
        filterable
      >
        <el-option label="全部岗位类别" value="" />
        <el-option
          v-for="item in options(facets.job_categories)"
          :key="item.value"
          :label="`${item.value}（${item.count}）`"
          :value="item.value"
        />
      </el-select>
    </div>
  </section>
</template>
