<script setup lang="ts">
import { computed } from 'vue'
import { ChevronRight } from '../../lib/cockpit-icons'
import { PROVIDER_ICON_COMPONENTS, PROVIDER_ICON_TONES } from '../../lib/cockpit-icons'
import { providerToneClass } from '../../lib/cockpit-ui'
import { PROVIDER_ORDER, type ProviderKey, useDashboardStore } from '../../stores/dashboard'
import { useUiStore } from '../../stores/ui'

const uiStore = useUiStore()
const dashboardStore = useDashboardStore()

const cards = computed(() => {
  const providers = dashboardStore.providers
  if (!providers) return []

  return PROVIDER_ORDER.map((key: ProviderKey) => {
    const item = providers[key]
    const statusKey =
      item.status === 'ready'
        ? 'Cockpit Status Ready'
        : item.status === 'blocked'
          ? 'Cockpit Status Blocked'
          : 'Cockpit Status Skipped'
    const detail =
      item.status === 'ready' ? item.detail : uiStore.tr(item.detail) || item.detail
    return {
      key,
      icon: PROVIDER_ICON_COMPONENTS[key],
      tone: PROVIDER_ICON_TONES[key],
      shortLabel: key.toUpperCase(),
      detail,
      status: uiStore.tr(statusKey),
      kind: item.status,
      selected: dashboardStore.selectedProvider === key,
    }
  })
})

function cardBorderClass(kind: string, selected: boolean) {
  if (selected) return 'border-indigo-400/50 ring-2 ring-indigo-500/25'
  if (kind === 'ready') return 'border-emerald-400/20 light:border-emerald-500/30'
  if (kind === 'blocked') return 'border-rose-400/30 light:border-rose-500/35'
  return 'border-slate-600/20 light:border-slate-200'
}

function statusTextClass(kind: string) {
  if (kind === 'ready') return 'text-emerald-400'
  if (kind === 'blocked') return 'text-rose-400'
  return 'text-slate-500'
}

function onCardClick(key: ProviderKey) {
  dashboardStore.toggleProvider(key)
}
</script>

<template>
  <section class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5" aria-label="Providers">
    <button
      v-for="card in cards"
      :key="card.key"
      type="button"
      class="group relative flex min-h-[6.75rem] flex-col rounded-xl border bg-cockpit-surface/75 p-3.5 text-left transition hover:border-slate-500/40 hover:bg-cockpit-elevated/80 light:border-slate-200 light:bg-white light:hover:border-slate-300 light:hover:bg-slate-50"
      :class="cardBorderClass(card.kind, card.selected)"
      :aria-expanded="card.selected"
      @click="onCardClick(card.key)"
    >
      <ChevronRight
        :size="14"
        class="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-600 transition group-hover:text-slate-400"
        :class="{ 'rotate-90 text-indigo-400': card.selected }"
      />
      <div class="mt-auto absolute top-1.5 right-3.5 border-slate-600/25 pt-2.5 light:border-slate-200">
        <div
          class="flex items-center gap-1.5 text-xs font-bold"
          :class="statusTextClass(card.kind)"
        >
          <span class="size-1.5 rounded-full bg-current" />
          {{ card.status }}
        </div>
      </div>
      <div class="mb-3 flex items-center gap-2 pr-5">
        <div
          class="grid size-8 shrink-0 place-items-center rounded-lg"
          :class="providerToneClass[card.tone]"
        >
          <component :is="card.icon" :size="18" :stroke-width="2" />
        </div>
        <div class="text-[0.64rem] font-extrabold tracking-widest text-slate-400 uppercase">
          {{ card.shortLabel }}
        </div>
      </div>
      <div class="mb-3 truncate text-sm font-medium text-slate-300 light:text-slate-700">
        {{ card.detail }}
      </div>
    </button>
    <div v-if="cards.length === 0" class="col-span-full py-4 text-slate-500">
      {{ dashboardStore.loading ? '…' : '—' }}
    </div>
  </section>
</template>
