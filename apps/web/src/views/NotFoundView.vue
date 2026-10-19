<template>
  <main class="page">
    <el-result icon="warning" title="页面不存在" sub-title="请返回职位列表继续浏览">
      <template #extra>
        <RouterLink to="/">
          <el-button type="primary">返回首页</el-button>
        </RouterLink>
      </template>
    </el-result>
  </main>
</template>

