<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { channelAvatarSrc, channelsApi, type ChannelSummary } from '../api/channels'
import { ApiError } from '../api/client'
import ChannelEditorModal from '../components/shell/ChannelEditorModal.vue'
import ChannelHistoryPanel from '../components/channels/ChannelHistoryPanel.vue'
import { useActiveChannelSwitch } from '../composables/useActiveChannelSwitch'
import { cardClass } from '../lib/cockpit-ui'
import { useChannelsStore } from '../stores/channels'
import { useDashboardStore } from '../stores/dashboard'
import { useWorkspaceStore } from '../stores/workspace'
import { useUiStore } from '../stores/ui'
import { Pencil, Plus, Trash2 } from '../lib/cockpit-icons'

const uiStore = useUiStore()
const channelsStore = useChannelsStore()
const workspaceStore = useWorkspaceStore()
const dashboardStore = useDashboardStore()
const { switchChannel } = useActiveChannelSwitch()

const modalOpen = ref(false)
const modalMode = ref<'create' | 'edit'>('create')
const modalSlug = ref<string | null>(null)
const errorMessage = ref<string | null>(null)
const deletingSlug = ref<string | null>(null)

onMounted(() => channelsStore.fetchChannels())

const activeChannel = computed(() =>
  channelsStore.channels.find((c) => c.slug === channelsStore.activeSlug),
)

function channelInitial(channel: ChannelSummary) {
  return (channel.name || channel.slug || '?').trim().charAt(0).toUpperCase()
}

function openCreate() {
  modalMode.value = 'create'
  modalSlug.value = null
  modalOpen.value = true
}

function openEdit(slug: string) {
  modalMode.value = 'edit'
  modalSlug.value = slug
  modalOpen.value = true
}

async function selectChannel(slug: string) {
  await switchChannel(slug)
}

async function removeChannel(slug: string) {
  if (!window.confirm(uiStore.tr('Cockpit Channel Delete Confirm'))) return
  errorMessage.value = null
  deletingSlug.value = slug
  try {
    await channelsApi.delete(slug)
    if (channelsStore.activeSlug === slug) {
      const next = channelsStore.channels.find((c) => c.slug !== slug)
      channelsStore.setActiveChannel(next?.slug ?? '')
    }
    await channelsStore.fetchChannels()
    if (channelsStore.activeSlug) {
      await workspaceStore.load(channelsStore.activeSlug)
    }
    await dashboardStore.refresh()
  } catch (err) {
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
  } finally {
    deletingSlug.value = null
  }
}

async function onSaved() {
  modalOpen.value = false
  await channelsStore.fetchChannels()
}
</script>

<template>
  <div class="flex w-full flex-col gap-5">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="cockpit-heading text-xl font-bold tracking-tight">{{ uiStore.tr('Cockpit Tab Channels') }}</h2>
        <p class="cockpit-muted mt-1 text-sm">{{ uiStore.tr('Cockpit Channels Subtitle') }}</p>
      </div>
      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 px-3.5 py-2 text-sm font-semibold text-white shadow-md shadow-indigo-500/20"
        @click="openCreate"
      >
        <Plus :size="14" />
        {{ uiStore.tr('Cockpit Channel New') }}
      </button>
    </div>

    <p v-if="errorMessage" class="text-sm text-rose-400">{{ errorMessage }}</p>

    <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
      <div
        v-for="channel in channelsStore.channels"
        :key="channel.slug"
        :class="[cardClass, 'flex items-center gap-3']"
        :aria-current="channel.slug === channelsStore.activeSlug"
        :style="channel.slug === channelsStore.activeSlug ? 'border-color: rgba(129,140,248,0.5)' : undefined"
      >
        <button type="button" class="flex min-w-0 flex-1 items-center gap-3 text-left" @click="selectChannel(channel.slug)">
          <div
            class="grid size-10 shrink-0 place-items-center overflow-hidden rounded-full bg-gradient-to-br from-rose-500/30 to-amber-400/30 text-sm font-bold text-orange-100"
          >
            <img
              v-if="channelAvatarSrc(channel)"
              :src="channelAvatarSrc(channel)!"
              :alt="channel.name"
              class="size-full object-cover"
            />
            <span v-else>{{ channelInitial(channel) }}</span>
          </div>
          <div class="min-w-0">
            <p class="cockpit-title truncate text-sm font-semibold">{{ channel.name }}</p>
            <p class="cockpit-muted truncate text-xs">{{ channel.slug }} · {{ channel.niche || '—' }}</p>
          </div>
        </button>
        <div class="flex shrink-0 items-center gap-1">
          <button
            type="button"
            class="grid size-8 place-items-center rounded-lg text-slate-500 hover:bg-slate-800/60 hover:text-slate-200 light:hover:bg-slate-100"
            :title="uiStore.tr('Cockpit Channel Edit')"
            @click="openEdit(channel.slug)"
          >
            <Pencil :size="14" />
          </button>
          <button
            type="button"
            class="grid size-8 place-items-center rounded-lg text-slate-500 hover:bg-rose-950/30 hover:text-rose-400 light:hover:bg-rose-50"
            :disabled="deletingSlug === channel.slug"
            :title="uiStore.tr('Cockpit Channel Delete')"
            @click="removeChannel(channel.slug)"
          >
            <Trash2 :size="14" />
          </button>
        </div>
      </div>
    </div>

    <div v-if="activeChannel" :class="cardClass">
      <p class="cockpit-muted mb-3 text-sm">
        {{ uiStore.tr('Cockpit Active Channel') }}: <strong class="cockpit-title">{{ activeChannel.name }}</strong>
      </p>
      <ChannelHistoryPanel />
    </div>

    <ChannelEditorModal
      :open="modalOpen"
      :mode="modalMode"
      :slug="modalSlug"
      @close="modalOpen = false"
      @saved="onSaved"
    />
  </div>
</template>
