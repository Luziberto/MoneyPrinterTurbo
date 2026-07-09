<script setup lang="ts">
import { onMounted, watch } from 'vue'
import AppHeader from './AppHeader.vue'
import CockpitDashboard from './CockpitDashboard.vue'
import TabNav from './TabNav.vue'
import { useChannelsStore } from '../../stores/channels'
import { useDashboardStore } from '../../stores/dashboard'
import { useUiStore } from '../../stores/ui'
import { useWorkspaceStore } from '../../stores/workspace'

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
    <AppHeader />
    <CockpitDashboard />
    <TabNav />
    <main class="flex-1 px-5 pt-2 pb-4">
      <RouterView />
    </main>
  </div>
</template>
