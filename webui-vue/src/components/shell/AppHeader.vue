<script setup lang="ts">
import { computed } from 'vue'
import ActiveChannelSelect from './ActiveChannelSelect.vue'
import { KNOWN_LOCALES, type LocaleCode } from '../../api/i18n'
import { useTheme } from '../../composables/useTheme'
import { useDashboardStore } from '../../stores/dashboard'
import { useUiStore } from '../../stores/ui'
import { useWorkspaceStore } from '../../stores/workspace'
import {
  Clapperboard,
  Clock,
  Globe,
  Moon,
  Play,
  RectangleVertical,
  Sparkles,
  Star,
  Sun,
} from '../../lib/cockpit-icons'

const APP_VERSION = '1.3.0'

const LOCALE_LABELS: Record<LocaleCode, string> = {
  de: 'Deutsch',
  en: 'English',
  es: 'Español',
  id: 'Bahasa Indonesia',
  pt: 'Português Brasileiro',
  ru: 'Русский',
  tr: 'Türkçe',
  vi: 'Tiếng Việt',
  zh: '中文',
}

const uiStore = useUiStore()
const workspaceStore = useWorkspaceStore()
const dashboardStore = useDashboardStore()
const { isDark, toggleTheme } = useTheme()

const metrics = computed(() => {
  const ws = workspaceStore.workspace
  const runtime = dashboardStore.channelRuntime ?? {}
  const targetClips =
    ws?.media.collector_target_clips ??
    (runtime.collector as { target_clips?: number } | undefined)?.target_clips ??
    25
  const aspect = ws?.media.video_aspect ?? String(runtime.video_aspect ?? '9:16')
  const duration = String(runtime.target_duration ?? '60-90')
  const durationLabel = duration.includes('s') ? duration : `${duration}s`
  return {
    clips: targetClips,
    aspect,
    duration: durationLabel,
    providers: `${dashboardStore.readyCount}/${dashboardStore.totalProviders}`,
  }
})

const headerMetrics = computed(() => [
  {
    key: 'clips',
    value: String(metrics.value.clips),
    label: uiStore.tr('Cockpit Header Videos Today'),
    icon: Clapperboard,
    iconClass:
      'bg-violet-500/15 text-violet-300 light:bg-violet-500/12 light:text-violet-600',
  },
  {
    key: 'aspect',
    value: metrics.value.aspect,
    label: uiStore.tr('Cockpit Header Format'),
    icon: RectangleVertical,
    iconClass:
      'bg-emerald-500/15 text-emerald-300 light:bg-emerald-500/12 light:text-emerald-600',
  },
  {
    key: 'duration',
    value: metrics.value.duration,
    label: uiStore.tr('Cockpit Header Duration'),
    icon: Clock,
    iconClass: 'bg-amber-500/15 text-amber-300 light:bg-amber-500/12 light:text-amber-600',
  },
  {
    key: 'status',
    value: metrics.value.providers,
    label: uiStore.tr('Cockpit Header Overall Status'),
    icon: Star,
    iconClass: 'bg-sky-500/15 text-sky-300 light:bg-sky-500/12 light:text-sky-600',
  },
])

const iconBtnClass =
  'grid size-10 place-items-center rounded-xl border border-slate-600/25 bg-cockpit-surface/80 text-slate-300 transition hover:border-slate-500/40 hover:bg-slate-800 hover:text-white light:border-slate-200 light:bg-white light:text-slate-600 light:hover:border-slate-300 light:hover:bg-slate-100 light:hover:text-slate-900'

const localeSelectClass =
  'w-full min-w-[12.5rem] appearance-none rounded-xl border border-slate-600/25 bg-cockpit-surface/80 py-2.5 pr-3 pl-9 text-sm text-slate-200 focus:border-indigo-400/50 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 light:border-slate-200 light:bg-white light:text-slate-800'

function localeOptionLabel(locale: LocaleCode) {
  return `${locale} — ${LOCALE_LABELS[locale]}`
}

function onLocaleChange(event: Event) {
  void uiStore.setLocale((event.target as HTMLSelectElement).value as LocaleCode)
}
</script>

<template>
  <header class="bg-cockpit-bg/95 light:bg-cockpit-bg">
    <div
      class="grid grid-cols-1 items-center gap-3 px-4 py-3.5 lg:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] lg:items-stretch lg:gap-4"
    >
      <!-- Brand -->
      <div class="flex min-w-0 items-center gap-3 lg:justify-self-start">
        <div class="relative shrink-0">
          <div
            class="grid size-12 place-items-center rounded-xl bg-gradient-to-br from-indigo-500 via-violet-600 to-fuchsia-600 text-white shadow-lg shadow-indigo-500/30"
          >
            <Play :size="20" :stroke-width="2.5" fill="currentColor" class="ml-0.5" />
          </div>
          <Sparkles
            :size="14"
            class="absolute -top-1 -right-1 text-amber-300 drop-shadow"
            :stroke-width="2.5"
          />
        </div>
        <div>
          <div class="flex flex-wrap items-center gap-2">
            <span class="cockpit-heading text-[1.05rem] font-bold tracking-tight">
              MoneyPrinterTurbo
            </span>
            <span
              class="rounded-md bg-sky-500/15 px-1.5 py-0.5 text-[0.68rem] font-semibold text-sky-300 light:text-sky-600"
            >
              v{{ APP_VERSION }}
            </span>
          </div>
          <p class="cockpit-muted mt-0.5 text-xs">
            {{ uiStore.tr('Cockpit Dashboard Tagline') }}
          </p>
        </div>
      </div>

      <!-- Canal ativo + specs — centro -->
      <div class="flex justify-center lg:justify-self-center lg:self-center">
        <div class="flex items-stretch gap-1">
          <ActiveChannelSelect variant="card" class="shrink-0" />

          <div
            class="flex h-full shrink-0 self-stretch rounded-xl border border-slate-600/25 bg-cockpit-surface/70 px-2.5 py-2 light:border-slate-200 light:bg-white"
          >
            <div class="grid h-full grid-cols-2 grid-rows-2 gap-x-3 gap-y-1">
              <div
                v-for="metric in headerMetrics"
                :key="metric.key"
                :title="metric.label"
                class="flex min-h-0 items-center gap-1.5"
              >
                <div
                  class="grid size-5 shrink-0 place-items-center rounded-md"
                  :class="metric.iconClass"
                >
                  <component :is="metric.icon" :size="11" :stroke-width="2.25" />
                </div>
                <div class="min-w-0 leading-none">
                  <div class="cockpit-title text-xs font-bold">{{ metric.value }}</div>
                  <div class="cockpit-muted mt-0.5 truncate text-[0.58rem]">{{ metric.label }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Controles — direita -->
      <div class="flex items-center justify-end gap-2 lg:justify-self-end lg:gap-3">
        <div class="relative shrink-0">
          <Globe
            :size="15"
            class="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-slate-500 light:text-slate-400"
          />
          <select :class="localeSelectClass" :value="uiStore.locale" @change="onLocaleChange">
            <option v-for="locale in KNOWN_LOCALES" :key="locale" :value="locale">
              {{ localeOptionLabel(locale) }}
            </option>
          </select>
        </div>
        <button
          type="button"
          :class="iconBtnClass"
          :title="uiStore.tr('Cockpit Toggle Theme')"
          @click="toggleTheme"
        >
          <Sun v-if="isDark" :size="18" />
          <Moon v-else :size="18" />
        </button>
      </div>
    </div>
    <div
      class="h-px w-full bg-gradient-to-r from-indigo-500/50 via-violet-500/25 to-emerald-500/50"
      aria-hidden="true"
    />
  </header>
</template>
