<script setup lang="ts">
import ProviderConfigPanel from './ProviderConfigPanel.vue'
import ProviderGrid from './ProviderGrid.vue'
</script>

<template>
  <section class="grid gap-4 px-5 py-3">
    <ProviderGrid />
    <ProviderConfigPanel />
  </section>
</template>
