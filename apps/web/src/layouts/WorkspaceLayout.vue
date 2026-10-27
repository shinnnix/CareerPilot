<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown, Menu, Setting, SwitchButton } from '@element-plus/icons-vue'

import { clearAccessToken, demoAuthEnabled, getAccessToken } from '@/auth-storage'
import NotificationsBell from '@/components/NotificationsBell.vue'
import WorkspaceSidebar from '@/components/WorkspaceSidebar.vue'
import { readSidebarCollapsed, writeSidebarCollapsed } from '@/composables/useSidebarCollapse'

const route = useRoute()
const router = useRouter()
const collapsed = ref(readSidebarCollapsed())
const narrow = ref(false)
const drawerOpen = ref(false)
const signedIn = ref(Boolean(getAccessToken()))

const breadcrumb = computed(() => ({
  group: typeof route.meta.group === 'string' ? route.meta.group : '',
  title: typeof route.meta.title === 'string' ? route.meta.title : '',
}))
const accountLabel = computed(() => {
  if (signedIn.value) return '已登录'
  return demoAuthEnabled() ? '演示账号' : '未登录'
})

let media: MediaQueryList | null = null

function toggleCollapse() {
  collapsed.value = !collapsed.value
  writeSidebarCollapsed(collapsed.value)
}

function handleMediaChange(event: MediaQueryListEvent) {
  narrow.value = event.matches
  if (!event.matches) drawerOpen.value = false
}

function logout() {
  clearAccessToken()
  signedIn.value = false
  router.push('/login')
}

onMounted(() => {
  signedIn.value = Boolean(getAccessToken())
  if (typeof window.matchMedia !== 'function') return
  media = window.matchMedia('(max-width: 1080px)')
  narrow.value = media.matches
  media.addEventListener('change', handleMediaChange)
})

onBeforeUnmount(() => {
  media?.removeEventListener('change', handleMediaChange)
})
</script>

<template>
  <div
    class="workspace-shell"
    :class="{
      'workspace-shell--collapsed': collapsed && !narrow,
      'workspace-shell--drawer-open': drawerOpen,
    }"
  >
    <WorkspaceSidebar
      :collapsed="collapsed && !narrow"
      :narrow="narrow"
      :open="drawerOpen"
      @toggle-collapse="toggleCollapse"
      @close="drawerOpen = false"
    />

    <div v-if="narrow && drawerOpen" class="workspace-backdrop" @click="drawerOpen = false" />

    <div class="workspace-body">
      <header class="workspace-topbar">
        <button
          v-if="narrow"
          type="button"
          class="workspace-menu-btn"
          aria-label="打开导航"
          @click="drawerOpen = true"
        >
          <el-icon><Menu /></el-icon>
        </button>

        <nav class="workspace-breadcrumb" aria-label="面包屑">
          <span v-if="breadcrumb.group">{{ breadcrumb.group }}</span>
          <span v-if="breadcrumb.group && breadcrumb.title">/</span>
          <strong v-if="breadcrumb.title">{{ breadcrumb.title }}</strong>
        </nav>

        <div class="workspace-topbar-actions">
          <NotificationsBell />
          <el-dropdown trigger="click">
            <button type="button" class="workspace-account">
              {{ accountLabel }}
              <el-icon><ArrowDown /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>账号与凭据只保存在本机</el-dropdown-item>
                <el-dropdown-item :icon="Setting" @click="router.push('/workspace/settings')">
                  AI 与设置
                </el-dropdown-item>
                <el-dropdown-item divided :icon="SwitchButton" @click="logout">
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main class="workspace-content">
        <RouterView />
      </main>
    </div>
  </div>
</template>
