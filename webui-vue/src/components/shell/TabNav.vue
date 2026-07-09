<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useUiStore } from '../../stores/ui'

const uiStore = useUiStore()
const route = useRoute()

const tabs = computed(() => [
  { to: '/criar/script', key: 'Cockpit Tab Create', prefix: '/criar' },
  { to: '/tarefas', key: 'Cockpit Tab Tasks', prefix: '/tarefas' },
  { to: '/historico', key: 'Cockpit Tab History', prefix: '/historico' },
])

function isActive(prefix: string) {
  return route.path === prefix || route.path.startsWith(`${prefix}/`)
}
</script>

<template>
  <nav class="flex gap-2 border-t border-slate-700/20 px-5 py-3.5 light:border-slate-200" aria-label="Cockpit tabs">
    <RouterLink
      v-for="tab in tabs"
      :key="tab.to"
      :to="tab.to"
      class="rounded-full border border-transparent px-4 py-2 text-sm font-semibold text-slate-500 no-underline transition hover:bg-slate-800/50 hover:text-slate-200 light:text-slate-600 light:hover:bg-slate-100 light:hover:text-slate-900"
      :class="{
        'border-indigo-400/40 bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-lg shadow-indigo-500/25':
          isActive(tab.prefix),
      }"
    >
      {{ uiStore.tr(tab.key) }}
    </RouterLink>
  </nav>
</template>
