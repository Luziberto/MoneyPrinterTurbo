<script setup lang="ts">
import { computed } from 'vue'
import { useUiStore } from '../../stores/ui'

const uiStore = useUiStore()

// Keys match webui/i18n/*.json exactly (see webui/Main.py's st.tabs call),
// so this is a mechanical lookup, not new translation content.
const tabs = computed(() => [
  { to: '/criar/script', key: 'Cockpit Tab Create' },
  { to: '/canais', key: 'Cockpit Tab Channels' },
  { to: '/tarefas', key: 'Cockpit Tab Tasks' },
  { to: '/config', key: 'Cockpit Tab Config' },
])
</script>

<template>
  <nav class="tab-nav">
    <RouterLink
      v-for="tab in tabs"
      :key="tab.to"
      :to="tab.to"
      class="tab-nav__item"
      :class="{ 'tab-nav__item--active': $route.path.startsWith(tab.to.split('/').slice(0, 2).join('/')) }"
    >
      {{ uiStore.tr(tab.key) }}
    </RouterLink>
  </nav>
</template>

<style scoped>
.tab-nav {
  display: flex;
  gap: 0.25rem;
}

.tab-nav__item {
  padding: 0.5rem 1rem;
  border-radius: 0.375rem;
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--cockpit-text-muted);
  text-decoration: none;
}

.tab-nav__item:hover {
  background: var(--cockpit-surface-hover);
}

.tab-nav__item--active {
  background: var(--cockpit-accent);
  color: var(--cockpit-accent-contrast);
}
</style>
