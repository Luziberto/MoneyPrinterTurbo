<script setup lang="ts">
import { onMounted } from 'vue'
import TabNav from './TabNav.vue'
import ChannelSwitcher from './ChannelSwitcher.vue'
import { useUiStore } from '../../stores/ui'
import { KNOWN_LOCALES, type LocaleCode } from '../../api/i18n'

const uiStore = useUiStore()

onMounted(() => {
  void uiStore.setLocale(uiStore.locale)
})

function onLocaleChange(event: Event) {
  void uiStore.setLocale((event.target as HTMLSelectElement).value as LocaleCode)
}
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
      <select class="locale-switcher" :value="uiStore.locale" @change="onLocaleChange">
        <option v-for="locale in KNOWN_LOCALES" :key="locale" :value="locale">{{ locale }}</option>
      </select>
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

.locale-switcher {
  margin-left: auto;
  padding: 0.35rem 0.5rem;
  border-radius: 0.375rem;
  border: 1px solid var(--cockpit-border);
  background: var(--cockpit-surface);
  color: var(--cockpit-text);
  font-size: 0.8rem;
  text-transform: uppercase;
}

.app-shell__body {
  flex: 1;
  padding: 1.5rem;
}
</style>
