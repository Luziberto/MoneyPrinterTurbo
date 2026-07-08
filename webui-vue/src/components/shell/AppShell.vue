<script setup lang="ts">
import TabNav from './TabNav.vue'
import ChannelSwitcher from './ChannelSwitcher.vue'
</script>

<template>
  <div class="app-shell">
    <header class="app-shell__header">
      <div class="app-shell__brand">
        <span class="app-shell__title">MoneyPrinterTurbo</span>
        <span class="app-shell__subtitle">Cockpit</span>
      </div>
      <TabNav />
      <ChannelSwitcher />
    </header>
    <main class="app-shell__body">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-shell__header {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 0.75rem 1.5rem;
  border-bottom: 1px solid var(--cockpit-border);
  background: var(--cockpit-surface);
}

.app-shell__brand {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
}

.app-shell__title {
  font-size: 1.15rem;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.app-shell__subtitle {
  font-size: 0.8rem;
  color: var(--cockpit-text-muted);
}

.app-shell__body {
  flex: 1;
  padding: 1.5rem;
}
</style>
