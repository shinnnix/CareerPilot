<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Briefcase, ChatDotRound, Connection, List, Plus, Reading, SwitchButton } from '@element-plus/icons-vue'
import { clearAccessToken, getAccessToken } from '@/auth-storage'

const router = useRouter()
const signedIn = ref(Boolean(getAccessToken()))
router.afterEach(() => { signedIn.value = Boolean(getAccessToken()) })

function logout() {
  clearAccessToken()
  router.push('/login')
}
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <RouterLink class="brand" to="/">
        <span class="brand-mark">CP</span>
        <span>
          <strong>CareerPilot</strong>
          <small>AI 求职决策工作台</small>
        </span>
      </RouterLink>
      <nav class="topbar-nav" aria-label="主导航">
        <RouterLink to="/">
          <el-icon><Briefcase /></el-icon>
          职位
        </RouterLink>
        <RouterLink to="/retrieval">
          <el-icon><Connection /></el-icon>
          检索实验室
        </RouterLink>
        <RouterLink to="/knowledge">
          <el-icon><Reading /></el-icon>
          知识库
        </RouterLink>
        <RouterLink to="/agent">
          <el-icon><ChatDotRound /></el-icon>
          Agent
        </RouterLink>
        <RouterLink to="/applications">
          <el-icon><List /></el-icon>
          申请
        </RouterLink>
        <RouterLink class="primary-link" to="/jobs/new">
          <el-icon><Plus /></el-icon>
          新建职位
        </RouterLink>
        <el-button v-if="signedIn" link :icon="SwitchButton" @click="logout">退出</el-button>
      </nav>
    </header>
    <RouterView />
  </div>
</template>
