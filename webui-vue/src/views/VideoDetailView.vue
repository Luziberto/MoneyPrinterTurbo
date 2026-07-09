<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { VueDatePicker } from '@vuepic/vue-datepicker'
import '@vuepic/vue-datepicker/dist/main.css'
import {
  videoLibraryApi,
  type VideoDetail,
  type VideoPublication,
} from '../api/videoLibrary'
import { ApiError } from '../api/client'
import { btnPrimaryClass, cardClass, inputClass } from '../lib/cockpit-ui'
import { useUiStore } from '../stores/ui'
import PlatformPicker from '../components/videos/PlatformPicker.vue'
import {
  Archive,
  ArrowLeft,
  Calendar,
  Check,
  FolderOpen,
  Pencil,
  RefreshCw,
  Send,
  Tag,
  Trash2,
  X,
} from '../lib/cockpit-icons'

const route = useRoute()
const router = useRouter()
const uiStore = useUiStore()

const videoId = computed(() => String(route.params.id))
const video = ref<VideoDetail | null>(null)
const loading = ref(false)
const errorMessage = ref<string | null>(null)
const actionBusy = ref(false)

const editingTitle = ref(false)
const titleDraft = ref('')
const editingCaption = ref(false)
const captionDraft = ref('')

const publishPlatforms = ref<string[]>([])
const scheduleMode = ref(false)
const scheduleAt = ref<Date | null>(null)

async function load() {
  loading.value = true
  errorMessage.value = null
  try {
    video.value = await videoLibraryApi.get(videoId.value)
    titleDraft.value = video.value.title
    captionDraft.value = video.value.caption
  } catch (err) {
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

onMounted(load)

function statusLabel(status: string) {
  const key = `Cockpit Video Status ${status.charAt(0).toUpperCase()}${status.slice(1)}`
  const translated = uiStore.tr(key)
  return translated === key ? status : translated
}

function formatBytes(bytes: number) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let value = bytes
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024
    i += 1
  }
  return `${value.toFixed(1)} ${units[i]}`
}

async function saveTitle() {
  if (!video.value) return
  actionBusy.value = true
  try {
    await videoLibraryApi.update(video.value.id, { title: titleDraft.value })
    editingTitle.value = false
    await load()
  } catch (err) {
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
  } finally {
    actionBusy.value = false
  }
}

async function saveCaption() {
  if (!video.value) return
  actionBusy.value = true
  try {
    await videoLibraryApi.update(video.value.id, { caption: captionDraft.value })
    editingCaption.value = false
    await load()
  } catch (err) {
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
  } finally {
    actionBusy.value = false
  }
}

async function publishNow() {
  if (!video.value || publishPlatforms.value.length === 0) return
  actionBusy.value = true
  errorMessage.value = null
  try {
    await videoLibraryApi.publish(video.value.id, publishPlatforms.value)
    publishPlatforms.value = []
    await load()
  } catch (err) {
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
  } finally {
    actionBusy.value = false
  }
}

async function confirmSchedule() {
  if (!video.value || publishPlatforms.value.length === 0 || !scheduleAt.value) return
  actionBusy.value = true
  errorMessage.value = null
  try {
    await videoLibraryApi.schedule(video.value.id, publishPlatforms.value, scheduleAt.value.toISOString())
    publishPlatforms.value = []
    scheduleAt.value = null
    scheduleMode.value = false
    await load()
  } catch (err) {
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
  } finally {
    actionBusy.value = false
  }
}

async function cancelPublication(pub: VideoPublication) {
  if (!video.value) return
  actionBusy.value = true
  try {
    await videoLibraryApi.cancelPublication(video.value.id, pub.id)
    await load()
  } catch (err) {
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
  } finally {
    actionBusy.value = false
  }
}

async function reRender() {
  if (!video.value) return
  actionBusy.value = true
  errorMessage.value = null
  try {
    const response = await videoLibraryApi.reRender(video.value.id)
    router.push(`/videos/${response.task_id}`)
  } catch (err) {
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
    actionBusy.value = false
  }
}

async function toggleArchive() {
  if (!video.value) return
  actionBusy.value = true
  try {
    if (video.value.status === 'archived') {
      await videoLibraryApi.restore(video.value.id)
    } else {
      await videoLibraryApi.archive(video.value.id)
    }
    await load()
  } catch (err) {
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
  } finally {
    actionBusy.value = false
  }
}

async function removeVideo() {
  if (!video.value) return
  if (!window.confirm(uiStore.tr('Cockpit Videos Delete Confirm'))) return
  actionBusy.value = true
  try {
    await videoLibraryApi.delete(video.value.id)
    router.push('/videos')
  } catch (err) {
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
    actionBusy.value = false
  }
}

function pubStatusClass(status: string) {
  if (status === 'published') return 'text-emerald-400'
  if (status === 'failed') return 'text-rose-400'
  if (status === 'cancelled') return 'cockpit-muted'
  return 'text-sky-400'
}

const canPublishActions = computed(() =>
  video.value ? ['ready', 'scheduled', 'published'].includes(video.value.status) : false,
)
</script>

<template>
  <div class="flex w-full flex-col gap-5">
    <RouterLink to="/videos" class="inline-flex w-fit items-center gap-1.5 text-sm text-slate-500 no-underline hover:text-slate-300">
      <ArrowLeft :size="14" />
      {{ uiStore.tr('Cockpit Tab Videos') }}
    </RouterLink>

    <p v-if="errorMessage" class="text-sm text-rose-400">{{ errorMessage }}</p>
    <p v-if="loading && !video" class="cockpit-muted text-sm">{{ uiStore.tr('Cockpit Loading') }}</p>

    <template v-if="video">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0 flex-1">
          <div v-if="editingTitle" class="flex items-center gap-2">
            <input v-model="titleDraft" :class="inputClass" class="max-w-md" />
            <button type="button" :class="btnPrimaryClass" :disabled="actionBusy" @click="saveTitle">
              <Check :size="15" />
            </button>
            <button type="button" class="cockpit-muted" @click="editingTitle = false">
              <X :size="15" />
            </button>
          </div>
          <h2 v-else class="cockpit-heading flex items-center gap-2 text-xl font-bold tracking-tight">
            {{ video.title || video.subject || video.id }}
            <button type="button" class="cockpit-muted hover:text-indigo-300" @click="editingTitle = true; titleDraft = video.title">
              <Pencil :size="14" />
            </button>
          </h2>
          <p class="cockpit-muted mt-1 text-xs">
            {{ video.channel_slug }} · {{ video.created_at }} ·
            <span class="font-semibold capitalize">{{ statusLabel(video.status) }}</span>
          </p>
        </div>

        <div class="flex flex-wrap gap-2">
          <button
            v-if="video.status === 'failed'"
            type="button"
            :class="btnPrimaryClass"
            :disabled="actionBusy"
            @click="reRender"
          >
            <RefreshCw :size="14" class="mr-1.5" />
            {{ uiStore.tr('Cockpit Videos Re Render') }}
          </button>
          <button
            v-if="['ready', 'scheduled', 'published', 'failed'].includes(video.status) || video.status === 'archived'"
            type="button"
            class="inline-flex items-center rounded-lg border border-slate-600/30 bg-slate-800/80 px-3.5 py-2 text-sm font-semibold text-slate-100 transition hover:bg-slate-700 disabled:opacity-55"
            :disabled="actionBusy"
            @click="toggleArchive"
          >
            <Archive :size="14" class="mr-1.5" />
            {{ video.status === 'archived' ? uiStore.tr('Cockpit Videos Restore') : uiStore.tr('Cockpit Videos Archive') }}
          </button>
          <button
            type="button"
            class="inline-flex items-center rounded-lg border border-rose-500/30 px-3.5 py-2 text-sm font-semibold text-rose-400 transition hover:bg-rose-950/30 disabled:opacity-55"
            :disabled="actionBusy"
            @click="removeVideo"
          >
            <Trash2 :size="14" class="mr-1.5" />
            {{ uiStore.tr('Cockpit Videos Delete') }}
          </button>
        </div>
      </div>

      <!-- Player -->
      <div class="overflow-hidden rounded-xl bg-black">
        <video v-if="video.video_path" :src="video.video_path" controls class="max-h-[32rem] w-full" />
        <div v-else class="flex h-48 items-center justify-center text-sm text-slate-500">
          {{ video.error || uiStore.tr('Cockpit Videos No Preview') }}
        </div>
      </div>

      <div class="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <!-- Script + keywords -->
        <section :class="cardClass">
          <h3 class="cockpit-title mb-2 text-sm font-bold">{{ uiStore.tr('Cockpit Script Section') }}</h3>
          <p v-if="video.script?.script" class="cockpit-muted whitespace-pre-wrap text-sm">{{ video.script.script }}</p>
          <p v-else class="cockpit-muted text-sm">{{ uiStore.tr('Cockpit Dashboard No Data') }}</p>
          <div v-if="video.keywords.length" class="mt-3 flex flex-wrap gap-1.5">
            <span
              v-for="(kw, i) in video.keywords"
              :key="i"
              class="inline-flex items-center gap-1 rounded-full bg-slate-800/60 px-2.5 py-1 text-xs light:bg-slate-100"
            >
              <Tag :size="10" />
              {{ typeof kw === 'string' ? kw : (kw as Record<string, unknown>).term }}
            </span>
          </div>
        </section>

        <!-- Caption -->
        <section :class="cardClass">
          <h3 class="cockpit-title mb-2 text-sm font-bold">{{ uiStore.tr('Cockpit Videos Caption') }}</h3>
          <div v-if="editingCaption" class="flex flex-col gap-2">
            <textarea v-model="captionDraft" :class="inputClass" rows="3" />
            <div class="flex gap-2">
              <button type="button" :class="btnPrimaryClass" :disabled="actionBusy" @click="saveCaption">
                {{ uiStore.tr('Cockpit Videos Save') }}
              </button>
              <button type="button" class="cockpit-muted text-sm" @click="editingCaption = false">
                {{ uiStore.tr('Cockpit Cancel') }}
              </button>
            </div>
          </div>
          <div v-else class="flex items-start justify-between gap-2">
            <p class="cockpit-muted whitespace-pre-wrap text-sm">{{ video.caption || '—' }}</p>
            <button type="button" class="cockpit-muted shrink-0 hover:text-indigo-300" @click="editingCaption = true">
              <Pencil :size="14" />
            </button>
          </div>
        </section>
      </div>

      <!-- Assets -->
      <section :class="cardClass">
        <h3 class="cockpit-title mb-2 flex items-center gap-2 text-sm font-bold">
          <FolderOpen :size="15" />
          {{ uiStore.tr('Cockpit Videos Assets') }}
        </h3>
        <ul v-if="video.assets.length" class="flex list-none flex-col gap-1.5 p-0 text-sm">
          <li
            v-for="asset in video.assets"
            :key="asset.name"
            class="flex items-center justify-between gap-2 rounded-lg border border-slate-600/15 px-3 py-2 light:border-slate-200"
          >
            <span class="truncate">
              <span class="cockpit-muted mr-2 text-xs uppercase">{{ asset.kind }}</span>
              {{ asset.name }}
            </span>
            <a :href="asset.url" download class="cockpit-muted shrink-0 text-xs text-indigo-400 no-underline hover:text-indigo-300">
              {{ formatBytes(asset.size_bytes) }}
            </a>
          </li>
        </ul>
        <p v-else class="cockpit-muted text-sm">{{ uiStore.tr('Cockpit Dashboard No Data') }}</p>
      </section>

      <!-- Publish / Schedule -->
      <section v-if="canPublishActions" :class="cardClass">
        <h3 class="cockpit-title mb-3 flex items-center gap-2 text-sm font-bold">
          <Send :size="15" />
          {{ uiStore.tr('Cockpit Videos Publish') }}
        </h3>
        <PlatformPicker v-model="publishPlatforms" />
        <div v-if="scheduleMode" class="mt-3 flex flex-wrap items-center gap-2">
          <VueDatePicker v-model="scheduleAt" :min-date="new Date()" model-type="date" />
          <button
            type="button"
            :class="btnPrimaryClass"
            :disabled="actionBusy || publishPlatforms.length === 0 || !scheduleAt"
            @click="confirmSchedule"
          >
            {{ uiStore.tr('Cockpit Videos Confirm Schedule') }}
          </button>
          <button type="button" class="cockpit-muted text-sm" @click="scheduleMode = false">
            {{ uiStore.tr('Cockpit Cancel') }}
          </button>
        </div>
        <div v-else class="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            :class="btnPrimaryClass"
            :disabled="actionBusy || publishPlatforms.length === 0"
            @click="publishNow"
          >
            {{ uiStore.tr('Cockpit Videos Publish Now') }}
          </button>
          <button
            type="button"
            class="inline-flex items-center gap-1.5 rounded-lg border border-slate-600/30 bg-slate-800/80 px-3.5 py-2 text-sm font-semibold text-slate-100 transition hover:bg-slate-700 disabled:opacity-55"
            :disabled="publishPlatforms.length === 0"
            @click="scheduleMode = true"
          >
            <Calendar :size="14" />
            {{ uiStore.tr('Cockpit Videos Schedule') }}
          </button>
        </div>
      </section>

      <!-- Publications -->
      <section :class="cardClass">
        <h3 class="cockpit-title mb-2 text-sm font-bold">{{ uiStore.tr('Cockpit Videos Publications') }}</h3>
        <ul v-if="video.publications.length" class="flex list-none flex-col gap-1.5 p-0 text-sm">
          <li
            v-for="pub in video.publications"
            :key="pub.id"
            class="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-600/15 px-3 py-2 light:border-slate-200"
          >
            <div class="min-w-0">
              <span class="font-semibold capitalize">{{ pub.platform }}</span>
              <span class="cockpit-muted ml-2 text-xs">{{ pub.provider }}</span>
              <span class="ml-2 text-xs font-semibold capitalize" :class="pubStatusClass(pub.status)">
                {{ pub.status }}
              </span>
              <span v-if="pub.scheduled_at" class="cockpit-muted ml-2 text-xs">{{ pub.scheduled_at }}</span>
              <p v-if="pub.error" class="mt-0.5 text-xs text-rose-400">{{ pub.error }}</p>
              <a v-if="pub.url" :href="pub.url" target="_blank" rel="noopener" class="text-xs text-indigo-400 no-underline hover:text-indigo-300">
                {{ pub.url }}
              </a>
            </div>
            <button
              v-if="['scheduled', 'publishing'].includes(pub.status)"
              type="button"
              class="cockpit-muted shrink-0 text-xs text-rose-400 hover:text-rose-300"
              :disabled="actionBusy"
              @click="cancelPublication(pub)"
            >
              {{ uiStore.tr('Cockpit Videos Cancel Publication') }}
            </button>
          </li>
        </ul>
        <p v-else class="cockpit-muted text-sm">{{ uiStore.tr('Cockpit Dashboard No Data') }}</p>
      </section>

      <!-- Events timeline -->
      <section :class="cardClass">
        <h3 class="cockpit-title mb-2 text-sm font-bold">{{ uiStore.tr('Cockpit Videos Timeline') }}</h3>
        <ul v-if="video.events.length" class="flex list-none flex-col gap-1.5 p-0 text-xs">
          <li v-for="event in video.events" :key="event.id" class="flex items-center gap-2">
            <span class="cockpit-muted">{{ event.created_at }}</span>
            <span class="font-semibold">{{ event.type }}</span>
            <span class="cockpit-muted">({{ event.actor }})</span>
          </li>
        </ul>
        <p v-else class="cockpit-muted text-sm">{{ uiStore.tr('Cockpit Dashboard No Data') }}</p>
      </section>
    </template>
  </div>
</template>
