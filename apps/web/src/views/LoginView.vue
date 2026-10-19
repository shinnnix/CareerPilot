<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { login, register } from '@/api/auth'
import { getApiErrorMessage } from '@/api/errors'
import { setAccessToken } from '@/auth-storage'

const route = useRoute()
const router = useRouter()
const mode = ref<'login' | 'register'>('login')
const loading = ref(false)
const form = reactive({ email: '', password: '' })

async function submit() {
  loading.value = true
  try {
    const result = mode.value === 'login'
      ? await login(form.email, form.password)
      : await register(form.email, form.password)
    setAccessToken(result.access_token)
    ElMessage.success(mode.value === 'login' ? '登录成功' : '账号创建成功')
    await router.replace(String(route.query.redirect || '/'))
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="page auth-page">
    <section class="surface auth-card">
      <p class="eyebrow">SECURE ACCESS</p>
      <h1>{{ mode === 'login' ? '登录项目工作台' : '创建账号' }}</h1>
      <p>职位、简历和申请记录按个人账号隔离。</p>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="邮箱">
          <el-input v-model="form.email" type="email" autocomplete="email" />
        </el-form-item>
        <el-form-item label="密码（至少 10 位）">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
          />
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading">
          {{ mode === 'login' ? '登录' : '注册并登录' }}
        </el-button>
        <el-button link @click="mode = mode === 'login' ? 'register' : 'login'">
          {{ mode === 'login' ? '没有账号？立即注册' : '已有账号？返回登录' }}
        </el-button>
      </el-form>
    </section>
  </main>
</template>

<style scoped>
.auth-page { display: grid; min-height: calc(100vh - 88px); place-items: center; }
.auth-card { max-width: 460px; padding: 36px; width: 100%; }
.auth-card h1 { margin: 6px 0 8px; }
.auth-card p { color: var(--text-muted); margin-bottom: 24px; }
</style>
