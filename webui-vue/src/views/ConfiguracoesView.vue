<script setup lang="ts">
import ProviderConfigPanel from '../components/shell/ProviderConfigPanel.vue'
import ProviderGrid from '../components/shell/ProviderGrid.vue'
import { useUiStore } from '../stores/ui'

const uiStore = useUiStore()
</script>

<template>
  <div class="flex w-full flex-col gap-4">
    <div>
      <h2 class="cockpit-heading text-xl font-bold tracking-tight">{{ uiStore.tr('Cockpit Tab Settings') }}</h2>
      <p class="cockpit-muted mt-1 text-sm">{{ uiStore.tr('Cockpit Settings Subtitle') }}</p>
    </div>
    <ProviderGrid />
    <ProviderConfigPanel />
  </div>
</template>
