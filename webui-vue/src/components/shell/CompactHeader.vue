<script setup lang="ts">
import ActiveChannelSelect from './ActiveChannelSelect.vue'
import { KNOWN_LOCALES, type LocaleCode } from '../../api/i18n'
import { useTheme } from '../../composables/useTheme'
import { useUiStore } from '../../stores/ui'
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  LayoutDashboard,
  Moon,
  Play,
  Radio,
  Settings,
  Sparkles,
  Sun,
  Video,
  List,
} from '../../lib/cockpit-icons'

const uiStore = useUiStore()
const route = useRoute()
const { isDark, toggleTheme } = useTheme()

const navItems = computed(() => [
  { to: '/', key: 'Cockpit Tab Dashboard', prefix: '/', icon: LayoutDashboard, exact: true },
  { to: '/criar', key: 'Cockpit Tab Create', prefix: '/criar', icon: Sparkles, exact: false },
  { to: '/videos', key: 'Cockpit Tab Videos', prefix: '/videos', icon: Video, exact: false },
  { to: '/tarefas', key: 'Cockpit Tab Tasks', prefix: '/tarefas', icon: List, exact: false },
  { to: '/canais', key: 'Cockpit Tab Channels', prefix: '/canais', icon: Radio, exact: false },
  { to: '/configuracoes', key: 'Cockpit Tab Settings', prefix: '/configuracoes', icon: Settings, exact: false },
])

function isActive(item: { prefix: string; exact: boolean }) {
  if (item.exact) return route.path === item.prefix
  return route.path === item.prefix || route.path.startsWith(`${item.prefix}/`)
}

const iconBtnClass =
  'grid size-9 shrink-0 place-items-center rounded-xl border border-slate-600/25 bg-cockpit-surface/80 text-slate-300 transition hover:border-slate-500/40 hover:bg-slate-800 hover:text-white light:border-slate-200 light:bg-white light:text-slate-600 light:hover:border-slate-300 light:hover:bg-slate-100 light:hover:text-slate-900'

const localeSelectClass =
  'w-full min-w-[9rem] appearance-none rounded-xl border border-slate-600/25 bg-cockpit-surface/80 py-2 pr-2.5 pl-2.5 text-xs text-slate-200 focus:border-indigo-400/50 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 light:border-slate-200 light:bg-white light:text-slate-800'

function onLocaleChange(event: Event) {
  void uiStore.setLocale((event.target as HTMLSelectElement).value as LocaleCode)
}
</script>

<template>
  <header class="bg-cockpit-bg/95 light:bg-cockpit-bg">
    <div class="flex flex-wrap items-center gap-3 px-4 py-2.5">
      <RouterLink to="/" class="flex shrink-0 items-center gap-2 no-underline">
        <div
          class="grid size-8 place-items-center rounded-lg bg-gradient-to-br from-indigo-500 via-violet-600 to-fuchsia-600 text-white shadow-md shadow-indigo-500/25"
        >
          <Play :size="14" :stroke-width="2.5" fill="currentColor" class="ml-0.5" />
        </div>
        <span class="cockpit-heading hidden text-sm font-bold tracking-tight sm:inline">
          MoneyPrinterTurbo
        </span>
      </RouterLink>

      <nav class="flex flex-1 flex-wrap items-center gap-1" aria-label="Main navigation">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="flex items-center gap-1.5 rounded-full border border-transparent px-3 py-1.5 text-xs font-semibold text-slate-500 no-underline transition hover:bg-slate-800/50 hover:text-slate-200 light:text-slate-600 light:hover:bg-slate-100 light:hover:text-slate-900"
          :class="{
            'border-indigo-400/40 bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-md shadow-indigo-500/25':
              isActive(item),
          }"
        >
          <component :is="item.icon" :size="13" :stroke-width="2.25" />
          {{ uiStore.tr(item.key) }}
        </RouterLink>
      </nav>

      <div class="flex shrink-0 items-center gap-2">
        <ActiveChannelSelect variant="inline" class="max-w-40 shrink-0 sm:max-w-56" />
        <select :class="localeSelectClass" :value="uiStore.locale" @change="onLocaleChange">
          <option v-for="locale in KNOWN_LOCALES" :key="locale" :value="locale">
            {{ locale.toUpperCase() }}
          </option>
        </select>
        <button
          type="button"
          :class="iconBtnClass"
          :title="uiStore.tr('Cockpit Toggle Theme')"
          @click="toggleTheme"
        >
          <Sun v-if="isDark" :size="16" />
          <Moon v-else :size="16" />
        </button>
      </div>
    </div>
    <div
      class="h-px w-full bg-gradient-to-r from-indigo-500/50 via-violet-500/25 to-emerald-500/50"
      aria-hidden="true"
    />
  </header>
</template>
