<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './AppHeader.vue'
import CompactHeader from './CompactHeader.vue'
import ProviderGrid from './ProviderGrid.vue'
import { useChannelsStore } from '../../stores/channels'
import { useDashboardStore } from '../../stores/dashboard'
import { useUiStore } from '../../stores/ui'
import { useWorkspaceStore } from '../../stores/workspace'

const route = useRoute()
const isDashboard = computed(() => route.path === '/')

const uiStore = useUiStore()
const channelsStore = useChannelsStore()
const workspaceStore = useWorkspaceStore()
const dashboardStore = useDashboardStore()

onMounted(async () => {
  await uiStore.setLocale(uiStore.locale)
  await channelsStore.fetchChannels()
  if (channelsStore.activeSlug) {
    await workspaceStore.load(channelsStore.activeSlug)
  }
  await dashboardStore.refresh()
})

watch(
  () => workspaceStore.workspace?.updated_at,
  () => {
    void dashboardStore.refresh()
  },
)

watch(
  () => channelsStore.activeSlug,
  async (slug) => {
    if (!slug) return
    await workspaceStore.load(slug)
    await dashboardStore.refresh()
  },
)
</script>

<template>
  <div class="flex min-h-screen flex-col bg-cockpit-bg light:bg-cockpit-bg">
    <template v-if="isDashboard">
      <AppHeader />
      <section class="px-5 py-3">
        <ProviderGrid />
      </section>
    </template>
    <CompactHeader v-else />
    <main class="flex-1 px-5 pt-2 pb-4">
      <RouterView />
    </main>
  </div>
</template>
