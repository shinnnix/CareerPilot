<script setup lang="ts">
import { reactive, watch } from 'vue'
import { Delete, Plus } from '@element-plus/icons-vue'

import type { InterviewRoundInput, StageKey } from '@/types/workspace'

const props = defineProps<{
  stage: StageKey
  payload: Record<string, unknown>
  occurredAt?: string | null
  saving?: boolean
  removable?: boolean
}>()

const emit = defineEmits<{
  (event: 'save', payload: Record<string, unknown>, occurredAt: string | null): void
  (event: 'remove'): void
}>()

const RESULTS = [
  { value: 'passed', label: '通过' },
  { value: 'failed', label: '未通过' },
  { value: 'unknown', label: '还不确定' },
]
const FORMATS = [
  { value: 'online', label: '线上' },
  { value: 'onsite', label: '现场' },
  { value: 'phone', label: '电话' },
]

const writtenTest = reactive({
  taken_at: '',
  duration_minutes: undefined as number | undefined,
  link: '',
  score: '',
  result: 'unknown',
  notes: '',
})

const interview = reactive({
  rounds: [] as InterviewRoundInput[],
  summary: '',
  result: 'unknown',
})

const offer = reactive({
  base_city: '',
  monthly: undefined as number | undefined,
  annual: undefined as number | undefined,
  bonus: undefined as number | undefined,
  start_date: '',
  reply_deadline: '',
  benefits: '',
  notes: '',
})

const occurredAt = reactive({ value: '' })

function toDisplayDateTime(value: unknown): string {
  if (typeof value !== 'string' || !value) return ''
  return value.slice(0, 19).replace('T', ' ')
}

function toDisplayDate(value: unknown): string {
  if (typeof value !== 'string' || !value) return ''
  return value.slice(0, 10)
}

function toIsoDateTime(value: string): string | null {
  if (!value) return null
  return value.replace(' ', 'T')
}

function asText(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function asNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined
}

function reset() {
  const payload = props.payload || {}
  occurredAt.value = toDisplayDateTime(props.occurredAt)

  if (props.stage === 'written_test') {
    writtenTest.taken_at = toDisplayDateTime(payload.taken_at)
    writtenTest.duration_minutes = asNumber(payload.duration_minutes)
    writtenTest.link = asText(payload.link)
    writtenTest.score = asText(payload.score)
    writtenTest.result = asText(payload.result) || 'unknown'
    writtenTest.notes = asText(payload.notes)
    return
  }

  if (props.stage === 'interview') {
    const rounds = Array.isArray(payload.rounds) ? (payload.rounds as Record<string, unknown>[]) : []
    interview.rounds = rounds.map((round, index) => ({
      index: asNumber(round.index) ?? index + 1,
      scheduled_at: toIsoDateTime(toDisplayDateTime(round.scheduled_at)),
      completed_at: toIsoDateTime(toDisplayDateTime(round.completed_at)),
      format: (asText(round.format) || null) as InterviewRoundInput['format'],
      interviewer: asText(round.interviewer),
      questions: Array.isArray(round.questions) ? (round.questions as string[]) : [],
      notes: asText(round.notes),
      self_rating: asNumber(round.self_rating) ?? null,
    }))
    if (!interview.rounds.length) addRound()
    interview.summary = asText(payload.summary)
    interview.result = asText(payload.result) || 'unknown'
    return
  }

  const salary = (payload.salary as Record<string, unknown> | undefined) || {}
  offer.base_city = asText(payload.base_city)
  offer.monthly = asNumber(salary.monthly)
  offer.annual = asNumber(salary.annual)
  offer.bonus = asNumber(salary.bonus)
  offer.start_date = toDisplayDate(payload.start_date)
  offer.reply_deadline = toDisplayDate(payload.reply_deadline)
  offer.benefits = asText(payload.benefits)
  offer.notes = asText(payload.notes)
}

function addRound() {
  interview.rounds.push({
    index: interview.rounds.length + 1,
    scheduled_at: null,
    completed_at: null,
    format: null,
    interviewer: '',
    questions: [],
    notes: '',
    self_rating: null,
  })
}

function removeRound(position: number) {
  interview.rounds.splice(position, 1)
  interview.rounds.forEach((round, index) => {
    round.index = index + 1
  })
}

function questionsText(round: InterviewRoundInput): string {
  return (round.questions || []).join('\n')
}

function setQuestions(round: InterviewRoundInput, value: string) {
  round.questions = value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

function build(): Record<string, unknown> {
  if (props.stage === 'written_test') {
    return {
      taken_at: toIsoDateTime(writtenTest.taken_at),
      duration_minutes: writtenTest.duration_minutes ?? null,
      link: writtenTest.link.trim() || null,
      score: writtenTest.score.trim() || null,
      result: writtenTest.result,
      notes: writtenTest.notes.trim() || null,
    }
  }

  if (props.stage === 'interview') {
    return {
      rounds: interview.rounds.map((round) => ({
        index: round.index,
        scheduled_at: round.scheduled_at || null,
        completed_at: round.completed_at || null,
        format: round.format || null,
        interviewer: round.interviewer || null,
        questions: round.questions || [],
        notes: round.notes || null,
        self_rating: round.self_rating ?? null,
      })),
      summary: interview.summary.trim() || null,
      result: interview.result,
    }
  }

  const salary = {
    monthly: offer.monthly ?? null,
    annual: offer.annual ?? null,
    bonus: offer.bonus ?? null,
  }
  const hasSalary = Object.values(salary).some((value) => value !== null)
  return {
    base_city: offer.base_city.trim() || null,
    salary: hasSalary ? salary : null,
    start_date: offer.start_date || null,
    reply_deadline: offer.reply_deadline || null,
    benefits: offer.benefits.trim() || null,
    notes: offer.notes.trim() || null,
  }
}

function save() {
  emit('save', build(), toIsoDateTime(occurredAt.value))
}

watch(() => [props.payload, props.occurredAt, props.stage], reset, {
  immediate: true,
  deep: true,
})
</script>

<template>
  <div class="stage-form">
    <el-form label-position="top" @submit.prevent="save">
      <template v-if="stage === 'written_test'">
        <div class="form-grid">
          <el-form-item label="笔试时间">
            <el-date-picker
              v-model="writtenTest.taken_at"
              type="datetime"
              value-format="YYYY-MM-DD HH:mm:ss"
              placeholder="选择时间"
            />
          </el-form-item>
          <el-form-item label="时长（分钟）">
            <el-input-number v-model="writtenTest.duration_minutes" :min="0" :max="1440" controls-position="right" />
          </el-form-item>
          <el-form-item label="结果">
            <el-select v-model="writtenTest.result">
              <el-option v-for="item in RESULTS" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="成绩">
            <el-input v-model="writtenTest.score" maxlength="50" placeholder="例如 88 / 通过" />
          </el-form-item>
        </div>
        <el-form-item label="笔试链接">
          <el-input v-model="writtenTest.link" maxlength="1000" placeholder="https://" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="writtenTest.notes" type="textarea" :rows="3" maxlength="5000" />
        </el-form-item>
      </template>

      <template v-else-if="stage === 'interview'">
        <div v-for="(round, position) in interview.rounds" :key="position" class="interview-round">
          <header class="interview-round-head">
            <strong>第 {{ position + 1 }} 轮</strong>
            <el-button
              v-if="interview.rounds.length > 1"
              link
              type="danger"
              :icon="Delete"
              @click="removeRound(position)"
            >
              移除
            </el-button>
          </header>
          <div class="form-grid">
            <el-form-item label="面试时间">
              <el-date-picker
                v-model="round.scheduled_at"
                type="datetime"
                value-format="YYYY-MM-DDTHH:mm:ss"
                placeholder="安排时间"
              />
            </el-form-item>
            <el-form-item label="完成时间">
              <el-date-picker
                v-model="round.completed_at"
                type="datetime"
                value-format="YYYY-MM-DDTHH:mm:ss"
                placeholder="面试完成时间"
              />
            </el-form-item>
            <el-form-item label="形式">
              <el-select v-model="round.format" clearable placeholder="线上 / 现场 / 电话">
                <el-option v-for="item in FORMATS" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="面试官">
              <el-input v-model="round.interviewer" maxlength="200" />
            </el-form-item>
            <el-form-item label="自评（1-5）">
              <el-input-number v-model="round.self_rating" :min="1" :max="5" controls-position="right" />
            </el-form-item>
          </div>
          <el-form-item label="面试问题（每行一条）">
            <el-input
              :model-value="questionsText(round)"
              type="textarea"
              :rows="3"
              maxlength="5000"
              @update:model-value="(value: string) => setQuestions(round, value)"
            />
          </el-form-item>
          <el-form-item label="本轮备注">
            <el-input v-model="round.notes" type="textarea" :rows="2" maxlength="2000" />
          </el-form-item>
        </div>
        <el-button :icon="Plus" size="small" @click="addRound">再加一轮</el-button>

        <el-form-item label="整体复盘" class="stage-form-gap">
          <el-input v-model="interview.summary" type="textarea" :rows="3" maxlength="5000" />
        </el-form-item>
        <el-form-item label="结果">
          <el-select v-model="interview.result">
            <el-option v-for="item in RESULTS" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
      </template>

      <template v-else>
        <div class="form-grid">
          <el-form-item label="Base 城市">
            <el-input v-model="offer.base_city" maxlength="50" placeholder="例如：深圳" />
          </el-form-item>
          <el-form-item label="入职时间">
            <el-date-picker v-model="offer.start_date" type="date" value-format="YYYY-MM-DD" />
          </el-form-item>
          <el-form-item label="答复截止">
            <el-date-picker v-model="offer.reply_deadline" type="date" value-format="YYYY-MM-DD" />
          </el-form-item>
          <el-form-item label="月薪">
            <el-input-number v-model="offer.monthly" :min="0" :max="10000000" controls-position="right" />
          </el-form-item>
          <el-form-item label="年薪">
            <el-input-number v-model="offer.annual" :min="0" :max="10000000" controls-position="right" />
          </el-form-item>
          <el-form-item label="奖金">
            <el-input-number v-model="offer.bonus" :min="0" :max="10000000" controls-position="right" />
          </el-form-item>
        </div>
        <el-form-item label="福利">
          <el-input v-model="offer.benefits" type="textarea" :rows="2" maxlength="2000" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="offer.notes" type="textarea" :rows="2" maxlength="5000" />
        </el-form-item>
      </template>

      <el-form-item label="发生时间（可选）">
        <el-date-picker
          v-model="occurredAt.value"
          type="datetime"
          value-format="YYYY-MM-DD HH:mm:ss"
          placeholder="默认现在"
        />
      </el-form-item>
    </el-form>

    <div class="stage-form-actions">
      <el-button v-if="removable" link type="danger" :icon="Delete" @click="emit('remove')">
        清空本阶段详情
      </el-button>
      <el-button type="primary" :loading="saving" @click="save">保存详情</el-button>
    </div>
  </div>
</template>
