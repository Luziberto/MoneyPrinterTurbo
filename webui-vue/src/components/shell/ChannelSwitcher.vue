<script setup lang="ts">
import { onMounted } from 'vue'
import { useChannelsStore } from '../../stores/channels'
import { useWorkspaceStore } from '../../stores/workspace'

const channelsStore = useChannelsStore()
const workspaceStore = useWorkspaceStore()

onMounted(async () => {
  await channelsStore.fetchChannels()
  if (channelsStore.activeSlug) {
    await workspaceStore.load(channelsStore.activeSlug)
  }
})

async function onChange(event: Event) {
  const slug = (event.target as HTMLSelectElement).value
  channelsStore.setActiveChannel(slug)
  await workspaceStore.load(slug)
}
</script>

<template>
  <select
    class="channel-switcher"
    :value="channelsStore.activeSlug ?? ''"
    :disabled="channelsStore.loading || channelsStore.channels.length === 0"
    @change="onChange"
  >
    <option v-if="channelsStore.channels.length === 0" value="">Sem canais</option>
    <option v-for="channel in channelsStore.channels" :key="channel.slug" :value="channel.slug">
      {{ channel.name }}
    </option>
  </select>
</template>

<style scoped>
.channel-switcher {
  padding: 0.4rem 0.6rem;
  border-radius: 0.375rem;
  border: 1px solid var(--cockpit-border);
  background: var(--cockpit-surface);
  color: var(--cockpit-text);
  font-size: 0.85rem;
  min-width: 10rem;
}
</style>
