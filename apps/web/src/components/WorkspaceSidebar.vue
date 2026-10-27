<script setup lang="ts">
import type { Component } from 'vue'
import {
  Briefcase,
  ChatDotRound,
  Connection,
  Expand,
  Fold,
  List,
  Notebook,
  Promotion,
  Reading,
  Setting,
  User,
} from '@element-plus/icons-vue'

withDefaults(
  defineProps<{
    collapsed?: boolean
    narrow?: boolean
    open?: boolean
  }>(),
  { collapsed: false, narrow: false, open: false },
)

const emit = defineEmits<{
  (event: 'toggle-collapse'): void
  (event: 'close'): void
}>()

interface SidebarItem {
  to: string
  label: string
  icon: Component
  ready?: boolean
}

interface SidebarGroup {
  label: string
  items: SidebarItem[]
}

const groups: SidebarGroup[] = [
  {
    label: '工作空间',
    items: [
      { to: '/workspace/jobs', label: '职位信息', icon: Briefcase },
      { to: '/workspace/applications', label: '投递记录', icon: List },
      { to: '/workspace/resumes', label: '我的简历', icon: Notebook },
    ],
  },
  {
    label: '更多工具',
    items: [
      { to: '/workspace/profile', label: '网申个人信息', icon: User },
      { to: '/workspace/extension', label: '网申填写插件', icon: Promotion },
      { to: '/workspace/library', label: '资料库', icon: Reading },
      { to: '/workspace/evidence', label: '证据检索', icon: Connection },
      { to: '/workspace/assistant', label: '求职 Agent', icon: ChatDotRound },
      { to: '/workspace/settings', label: 'AI 与设置', icon: Setting },
    ],
  },
]
</script>

<template>
  <aside class="workspace-sidebar" :class="{ 'workspace-sidebar--open': open }">
    <div class="workspace-sidebar-head">
      <RouterLink class="brand" to="/workspace/jobs" @click="emit('close')">
        <span class="brand-mark">CP</span>
        <span v-if="!collapsed">
          <strong>CareerPilot</strong>
          <small>求职工作台</small>
        </span>
      </RouterLink>
      <button
        v-if="!narrow"
        type="button"
        class="workspace-sidebar-toggle"
        :title="collapsed ? '展开侧栏' : '收起侧栏'"
        :aria-label="collapsed ? '展开侧栏' : '收起侧栏'"
        @click="emit('toggle-collapse')"
      >
        <el-icon>
          <Expand v-if="collapsed" />
          <Fold v-else />
        </el-icon>
      </button>
    </div>

    <nav class="workspace-sidebar-nav" aria-label="工作空间导航">
      <div v-for="group in groups" :key="group.label" class="sidebar-group">
        <p class="sidebar-group-label">{{ group.label }}</p>
        <ul>
          <li v-for="item in group.items" :key="item.label">
            <RouterLink
              v-if="item.ready !== false"
              class="sidebar-item"
              :to="item.to"
              @click="emit('close')"
            >
              <el-icon><component :is="item.icon" /></el-icon>
              <span class="sidebar-item-label">{{ item.label }}</span>
            </RouterLink>
            <span
              v-else
              class="sidebar-item sidebar-item--disabled"
              aria-disabled="true"
              :title="`${item.label}即将上线`"
            >
              <el-icon><component :is="item.icon" /></el-icon>
              <span class="sidebar-item-label">{{ item.label }}</span>
              <span v-if="!collapsed" class="sidebar-item-tag">待上线</span>
            </span>
          </li>
        </ul>
      </div>
    </nav>

    <p class="workspace-sidebar-foot">
      专注下一次机会<br />
      把每次投递都变成可复盘的进展。
    </p>
  </aside>
</template>
