<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useDashboardStore } from '../../stores/dashboard'
import { useUiStore } from '../../stores/ui'
import { List, Zap } from '../../lib/cockpit-icons'

const uiStore = useUiStore()
const dashboardStore = useDashboardStore()
const router = useRouter()

function viewLogs() {
  void router.push('/tarefas')
}
</script>

<template>
  <footer
    class="mt-auto flex items-center justify-between gap-4 border-t border-slate-600/15 bg-cockpit-bg/85 px-5 py-3 text-sm text-slate-500 light:border-slate-200 light:bg-cockpit-bg"
  >
    <div class="flex items-center gap-2 text-slate-400">
      <Zap :size="16" class="shrink-0 text-amber-400" />
      <span>
        {{ uiStore.tr('Cockpit System Status Footer') }}
        <template v-if="dashboardStore.allReady"> · {{ uiStore.tr('Cockpit Last Check') }}</template>
      </span>
    </div>
    <button
      type="button"
      class="cockpit-chrome inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm transition light:hover:bg-slate-100"
      @click="viewLogs"
    >
      <List :size="15" />
      {{ uiStore.tr('Cockpit View Logs') }}
    </button>
  </footer>
</template>
