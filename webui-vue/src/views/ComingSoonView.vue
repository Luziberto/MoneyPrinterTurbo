<script setup lang="ts">
import { useUiStore } from '../stores/ui'

defineProps<{ titleKey: string }>()

const uiStore = useUiStore()
</script>

<template>
  <div class="flex min-h-[20rem] flex-col items-center justify-center gap-2 text-center">
    <h2 class="cockpit-heading text-xl font-bold tracking-tight">{{ uiStore.tr(titleKey) }}</h2>
    <p class="cockpit-muted text-sm">{{ uiStore.tr('Cockpit Coming Soon') }}</p>
  </div>
</template>
