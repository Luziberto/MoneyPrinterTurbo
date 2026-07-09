<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { videoLibraryApi, type VideoRow, type VideoStatus } from '../api/videoLibrary'
import { ApiError } from '../api/client'
import { cardClass } from '../lib/cockpit-ui'
import { useUiStore } from '../stores/ui'
import { Archive, Clock, RefreshCw, Trash2, Video } from '../lib/cockpit-icons'

const uiStore = useUiStore()

const TABS: { value: VideoStatus | 'all'; key: string }[] = [
  { value: 'all', key: 'Cockpit Videos Tab All' },
  { value: 'draft', key: 'Cockpit Video Status Draft' },
  { value: 'rendering', key: 'Cockpit Video Status Rendering' },
  { value: 'ready', key: 'Cockpit Video Status Ready' },
  { value: 'scheduled', key: 'Cockpit Video Status Scheduled' },
  { value: 'published', key: 'Cockpit Video Status Published' },
  { value: 'archived', key: 'Cockpit Video Status Archived' },
  { value: 'failed', key: 'Cockpit Video Status Failed' },
]

const activeTab = ref<VideoStatus | 'all'>('all')
const videos = ref<VideoRow[]>([])
const total = ref(0)
const loading = ref(false)
const errorMessage = ref<string | null>(null)
const busyIds = ref<Set<string>>(new Set())

async function load() {
  loading.value = true
  errorMessage.value = null
  try {
    const result = await videoLibraryApi.list({
      status: activeTab.value === 'all' ? undefined : activeTab.value,
      page: 1,
      page_size: 60,
    })
    videos.value = result.videos
    total.value = result.total
  } catch (err) {
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(activeTab, load)

function statusLabel(status: string) {
  const key = `Cockpit Video Status ${status.charAt(0).toUpperCase()}${status.slice(1)}`
  const translated = uiStore.tr(key)
  return translated === key ? status : translated
}

function statusToneClass(status: string) {
  if (status === 'published') return 'text-emerald-400'
  if (status === 'failed') return 'text-rose-400'
  if (status === 'scheduled' || status === 'rendering') return 'text-sky-400'
  if (status === 'archived') return 'cockpit-muted'
  return 'text-slate-400'
}

function formatDuration(seconds: number | null) {
  if (!seconds) return '—'
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

function formatSize(bytes: number | null) {
  if (!bytes) return '—'
  const mb = bytes / (1024 * 1024)
  return `${mb.toFixed(1)} MB`
}

async function withBusy(id: string, action: () => Promise<void>) {
  busyIds.value.add(id)
  try {
    await action()
  } catch (err) {
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
  } finally {
    busyIds.value.delete(id)
  }
}

function reRender(video: VideoRow) {
  void withBusy(video.id, async () => {
    await videoLibraryApi.reRender(video.id)
    await load()
  })
}

function archive(video: VideoRow) {
  if (!window.confirm(uiStore.tr('Cockpit Videos Archive Confirm'))) return
  void withBusy(video.id, async () => {
    await videoLibraryApi.archive(video.id)
    await load()
  })
}

function remove(video: VideoRow) {
  if (!window.confirm(uiStore.tr('Cockpit Videos Delete Confirm'))) return
  void withBusy(video.id, async () => {
    await videoLibraryApi.delete(video.id)
    await load()
  })
}

const iconBtnClass =
  'grid size-7 place-items-center rounded-lg border border-slate-600/25 bg-cockpit-surface/70 text-slate-400 transition hover:border-indigo-400/40 hover:text-indigo-300 disabled:cursor-default disabled:opacity-40 light:border-slate-200 light:bg-white'

const emptyMessage = computed(() =>
  loading.value ? uiStore.tr('Cockpit Loading') : uiStore.tr('Cockpit Videos Empty'),
)
</script>

<template>
  <div class="flex w-full flex-col gap-4">
    <div>
      <h2 class="cockpit-heading text-xl font-bold tracking-tight">{{ uiStore.tr('Cockpit Tab Videos') }}</h2>
      <p class="cockpit-muted mt-1 text-sm">{{ uiStore.tr('Cockpit Videos Subtitle') }}</p>
    </div>

    <nav class="flex flex-wrap gap-1.5" aria-label="Video status filter">
      <button
        v-for="tab in TABS"
        :key="tab.value"
        type="button"
        class="rounded-full border border-transparent px-3.5 py-1.5 text-xs font-semibold text-slate-500 transition hover:bg-slate-800/50 hover:text-slate-200 light:text-slate-600 light:hover:bg-slate-100"
        :class="{
          'border-indigo-400/40 bg-gradient-to-br from-indigo-500 to-violet-600 text-white':
            activeTab === tab.value,
        }"
        @click="activeTab = tab.value"
      >
        {{ uiStore.tr(tab.key) }}
      </button>
    </nav>

    <p v-if="errorMessage" class="text-sm text-rose-400">{{ errorMessage }}</p>

    <p v-if="videos.length === 0" class="cockpit-muted text-sm">{{ emptyMessage }}</p>

    <div v-else class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <div v-for="video in videos" :key="video.id" :class="[cardClass, 'flex flex-col gap-2.5']">
        <RouterLink :to="`/videos/${video.id}`" class="block no-underline">
          <div class="flex aspect-video items-center justify-center overflow-hidden rounded-lg bg-slate-900/60 light:bg-slate-100">
            <img
              v-if="video.thumbnail_path"
              :src="video.thumbnail_path"
              :alt="video.title"
              class="size-full object-cover"
            />
            <Video v-else :size="28" class="text-slate-600" />
          </div>
        </RouterLink>

        <RouterLink :to="`/videos/${video.id}`" class="no-underline">
          <p class="cockpit-title truncate text-sm font-semibold">
            {{ video.title || video.subject || video.id }}
          </p>
        </RouterLink>

        <div class="flex items-center justify-between gap-2 text-xs">
          <span class="cockpit-muted truncate">{{ video.channel_slug }}</span>
          <span class="font-semibold capitalize" :class="statusToneClass(video.status)">
            {{ statusLabel(video.status) }}
          </span>
        </div>

        <div class="cockpit-muted flex items-center gap-2 text-xs">
          <Clock :size="12" />
          {{ formatDuration(video.duration_seconds) }}
          <span>·</span>
          {{ formatSize(video.file_size_bytes) }}
        </div>

        <p v-if="video.error" class="truncate text-xs text-rose-400">{{ video.error }}</p>

        <div class="mt-1 flex items-center gap-1.5">
          <button
            v-if="video.status === 'failed'"
            type="button"
            :class="iconBtnClass"
            :disabled="busyIds.has(video.id)"
            :title="uiStore.tr('Cockpit Videos Re Render')"
            @click="reRender(video)"
          >
            <RefreshCw :size="13" />
          </button>
          <button
            v-if="['ready', 'scheduled', 'published', 'failed'].includes(video.status)"
            type="button"
            :class="iconBtnClass"
            :disabled="busyIds.has(video.id)"
            :title="uiStore.tr('Cockpit Videos Archive')"
            @click="archive(video)"
          >
            <Archive :size="13" />
          </button>
          <button
            type="button"
            :class="iconBtnClass"
            :disabled="busyIds.has(video.id)"
            :title="uiStore.tr('Cockpit Videos Delete')"
            @click="remove(video)"
          >
            <Trash2 :size="13" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
