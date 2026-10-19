import { defineStore } from 'pinia'
import { ref } from 'vue'

export const usePreferencesStore = defineStore('preferences', () => {
  const pageSize = ref(9)

  function setPageSize(value: number) {
    pageSize.value = value
  }

  return { pageSize, setPageSize }
})

