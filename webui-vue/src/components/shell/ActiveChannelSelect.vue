<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { channelAvatarSrc, channelsApi, type ChannelSummary } from '../../api/channels'
import { ApiError } from '../../api/client'
import { useActiveChannelSwitch } from '../../composables/useActiveChannelSwitch'
import { formatTargetDurationLabel } from '../../lib/target-duration'
import { useChannelsStore } from '../../stores/channels'
import { useDashboardStore } from '../../stores/dashboard'
import { useUiStore } from '../../stores/ui'
import { useWorkspaceStore } from '../../stores/workspace'
import ChannelEditorModal from './ChannelEditorModal.vue'
import { ChevronDown, Plus, Settings, Trash2 } from '../../lib/cockpit-icons'

const props = withDefaults(defineProps<{ variant?: 'card' | 'inline' }>(), {
  variant: 'inline',
})

const uiStore = useUiStore()
const channelsStore = useChannelsStore()
const workspaceStore = useWorkspaceStore()
const dashboardStore = useDashboardStore()
const { switchChannel } = useActiveChannelSwitch()

const open = ref(false)
const rootEl = ref<HTMLElement | null>(null)
const modalOpen = ref(false)
const modalMode = ref<'create' | 'edit'>('edit')
const deleting = ref(false)
const actionError = ref<string | null>(null)

const activeChannel = computed(() =>
  channelsStore.channels.find((c) => c.slug === channelsStore.activeSlug),
)

const channelMeta = computed(() => {
  const runtime = dashboardStore.channelRuntime ?? {}
  const config = dashboardStore.channelConfig ?? {}
  const ws = workspaceStore.workspace
  const aspect = String(ws?.media.video_aspect ?? runtime.video_aspect ?? '9:16')
  const duration = formatTargetDurationLabel(String(runtime.target_duration ?? '60-90'))
  const lang = String(config.video_language ?? ws?.script.video_language ?? 'pt-BR')
  const llm = String(dashboardStore.providers?.llm?.detail ?? '—')
  return `${aspect} • ${duration} • ${llm} • ${lang}`
})

const cardGearBtnClass =
  'grid size-9 shrink-0 place-items-center rounded-lg border border-slate-600/25 bg-cockpit-surface/80 text-slate-300 transition hover:border-indigo-400/40 hover:bg-indigo-500/10 hover:text-indigo-300 light:border-slate-200 light:bg-white light:text-slate-600 light:hover:border-indigo-200 light:hover:bg-indigo-50 light:hover:text-indigo-600'

function channelInitial(channel: ChannelSummary) {
  const name = channel.name || channel.slug || '?'
  return name.trim().charAt(0).toUpperCase()
}

function avatarFor(channel: ChannelSummary) {
  return channelAvatarSrc(channel)
}

async function selectChannel(slug: string) {
  open.value = false
  await switchChannel(slug)
}

function openEdit() {
  if (!channelsStore.activeSlug) return
  open.value = false
  modalMode.value = 'edit'
  modalOpen.value = true
}

function openCreate() {
  open.value = false
  modalMode.value = 'create'
  modalOpen.value = true
}

async function removeActive() {
  const slug = channelsStore.activeSlug
  if (!slug) return
  if (!window.confirm(uiStore.tr('Cockpit Channel Delete Confirm'))) return
  actionError.value = null
  open.value = false
  deleting.value = true
  try {
    await channelsApi.delete(slug)
    if (channelsStore.activeSlug === slug) {
      const next = channelsStore.channels.find((c) => c.slug !== slug)
      channelsStore.setActiveChannel(next?.slug ?? '')
    }
    await channelsStore.fetchChannels()
    dashboardStore.closeProvider()
    if (channelsStore.activeSlug) {
      await workspaceStore.load(channelsStore.activeSlug)
    } else {
      workspaceStore.channelSlug = null
      workspaceStore.workspace = null
      workspaceStore.steps = null
    }
    await dashboardStore.refresh()
  } catch (err) {
    actionError.value = err instanceof ApiError ? err.message : String(err)
  } finally {
    deleting.value = false
  }
}

function onDocumentClick(event: MouseEvent) {
  if (!open.value || !rootEl.value) return
  if (!rootEl.value.contains(event.target as Node)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('click', onDocumentClick))
onUnmounted(() => document.removeEventListener('click', onDocumentClick))
</script>

<template>
  <div ref="rootEl" class="relative min-w-0" :class="variant === 'card' ? 'shrink-0' : ''">
    <!-- Card variant (header) -->
    <div
      v-if="variant === 'card' && activeChannel"
      class="flex items-stretch gap-0 rounded-xl border border-slate-600/25 bg-cockpit-surface/70 py-2.5 px-2.5 light:border-slate-200 light:bg-white"
    >
      <button
        type="button"
        class="flex min-w-0 flex-1 items-center gap-3 text-left transition hover:opacity-90 pr-2"
        :aria-expanded="open"
        aria-haspopup="menu"
        @click.stop="open = !open"
      >
        <div
          class="grid size-11 shrink-0 place-items-center overflow-hidden rounded-full bg-gradient-to-br from-rose-500/30 via-orange-400/25 to-amber-400/30 text-base font-bold text-orange-100 ring-2 ring-slate-700/50 light:ring-slate-200"
        >
          <img
            v-if="avatarFor(activeChannel)"
            :src="avatarFor(activeChannel)!"
            :alt="activeChannel.name"
            class="size-full object-cover"
          />
          <span v-else>{{ channelInitial(activeChannel) }}</span>
        </div>
        <div class="min-w-0 flex-1">
          <div
            class="text-[0.62rem] font-extrabold tracking-[0.14em] text-slate-500 uppercase light:text-slate-500"
          >
            {{ uiStore.tr('Cockpit Active Channel') }}
          </div>
          <div class="flex min-w-0 items-center gap-1">
            <span class="cockpit-title truncate text-sm font-bold">{{ activeChannel.name }}</span>
            <ChevronDown
              :size="14"
              class="shrink-0 text-slate-500 transition"
              :class="{ 'rotate-180 text-indigo-400': open }"
            />
          </div>
          <span
            class="mt-0.5 inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-400 light:text-emerald-600"
          >
            <span class="size-1.5 rounded-full bg-current shadow-[0_0_0_4px_rgba(74,222,128,0.12)]" />
            {{ uiStore.tr('Cockpit Channel Active') }}
          </span>
        </div>
      </button>
      <div
        class="-my-2.5 w-px shrink-0 self-stretch bg-slate-600/45 light:bg-slate-300"
        aria-hidden="true"
      />
      <button
        type="button"
        :class="[cardGearBtnClass, 'ml-2 self-center']"
        :title="uiStore.tr('Cockpit Channel Edit')"
        @click.stop="openEdit"
      >
        <Settings :size="16" />
      </button>
    </div>

    <button
      v-else-if="variant === 'card'"
      type="button"
      class="inline-flex items-center gap-2 rounded-xl border border-dashed border-slate-600/30 px-4 py-3 text-sm text-indigo-400 transition hover:border-indigo-400/40 hover:bg-indigo-500/5 light:border-slate-300"
      @click.stop="openCreate"
    >
      <Plus :size="16" />
      {{ uiStore.tr('Cockpit Channel New') }}
    </button>

    <!-- Inline variant -->
    <template v-else>
      <button
        v-if="activeChannel"
        type="button"
        class="flex max-w-full items-center gap-2 rounded-md px-1 py-0.5 text-left transition hover:bg-slate-800/40 light:hover:bg-slate-100"
        :aria-expanded="open"
        aria-haspopup="menu"
        @click.stop="open = !open"
      >
        <div
          class="grid size-7 shrink-0 place-items-center overflow-hidden rounded-full bg-gradient-to-br from-rose-500/30 to-amber-400/30 text-xs font-bold text-orange-100 ring-1 ring-slate-600/40 light:ring-slate-200"
        >
          <img
            v-if="avatarFor(activeChannel)"
            :src="avatarFor(activeChannel)!"
            :alt="activeChannel.name"
            class="size-full object-cover"
          />
          <span v-else>{{ channelInitial(activeChannel) }}</span>
        </div>
        <span class="cockpit-title inline-flex min-w-0 items-center gap-1 text-sm font-semibold">
          <span class="truncate">{{ activeChannel.name }}</span>
          <ChevronDown
            :size="14"
            class="shrink-0 text-slate-500 transition"
            :class="{ 'rotate-180 text-indigo-400': open }"
          />
        </span>
        <span class="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-emerald-500">
          <span class="size-1.5 rounded-full bg-current" />
          {{ uiStore.tr('Cockpit Channel Active') }}
        </span>
        <span class="cockpit-muted hidden truncate text-xs lg:inline">{{ channelMeta }}</span>
      </button>

      <button
        v-else
        type="button"
        class="inline-flex items-center gap-1.5 rounded-md px-1 py-0.5 text-sm text-indigo-400 hover:bg-slate-800/40 light:hover:bg-slate-100"
        @click.stop="openCreate"
      >
        <Plus :size="14" />
        {{ uiStore.tr('Cockpit Channel New') }}
      </button>

      <p v-if="activeChannel" class="cockpit-muted truncate pl-9 text-xs lg:hidden">{{ channelMeta }}</p>
    </template>

    <div
      v-if="open"
      class="absolute top-[calc(100%+0.25rem)] z-50 w-64 overflow-hidden rounded-lg border border-slate-600/25 bg-cockpit-elevated shadow-xl shadow-black/30 light:border-slate-200 light:bg-white"
      :class="
        variant === 'card'
          ? 'left-1/2 right-auto -translate-x-1/2'
          : 'left-0'
      "
      role="menu"
    >
      <div class="max-h-48 overflow-y-auto py-1" role="listbox">
        <button
          v-for="channel in channelsStore.channels"
          :key="channel.slug"
          type="button"
          role="option"
          class="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm transition hover:bg-indigo-500/10 light:hover:bg-indigo-50"
          :class="{ 'bg-indigo-500/10': channel.slug === channelsStore.activeSlug }"
          @click="selectChannel(channel.slug)"
        >
          <div
            class="grid size-7 shrink-0 place-items-center overflow-hidden rounded-full bg-gradient-to-br from-rose-500/30 to-amber-400/30 text-xs font-bold"
          >
            <img
              v-if="avatarFor(channel)"
              :src="avatarFor(channel)!"
              :alt="channel.name"
              class="size-full object-cover"
            />
            <span v-else>{{ channelInitial(channel) }}</span>
          </div>
          <div class="min-w-0 flex-1">
            <div class="truncate font-medium">{{ channel.name }}</div>
            <div class="cockpit-muted truncate text-xs">{{ channel.slug }}</div>
          </div>
        </button>
      </div>
      <div class="border-t border-slate-600/20 py-1 light:border-slate-200">
        <button
          type="button"
          class="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-slate-300 hover:bg-slate-800/50 light:text-slate-700 light:hover:bg-slate-100"
          @click="openCreate"
        >
          <Plus :size="14" />
          {{ uiStore.tr('Cockpit Channel New') }}
        </button>
        <button
          type="button"
          class="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-slate-500 hover:bg-rose-950/30 hover:text-rose-300 light:hover:bg-rose-50 light:hover:text-rose-600"
          :disabled="!channelsStore.activeSlug || deleting"
          @click="removeActive"
        >
          <Trash2 :size="14" />
          {{ uiStore.tr('Cockpit Channel Delete') }}
        </button>
      </div>
    </div>

    <p v-if="actionError" class="absolute top-full left-0 mt-0.5 text-xs text-rose-400">
      {{ actionError }}
    </p>

    <ChannelEditorModal
      :open="modalOpen"
      :mode="modalMode"
      :slug="channelsStore.activeSlug"
      @close="modalOpen = false"
      @saved="modalOpen = false"
    />
  </div>
</template>
