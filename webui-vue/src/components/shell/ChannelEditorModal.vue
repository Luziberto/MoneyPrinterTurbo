<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { channelAvatarSrc, type ChannelSummary } from '../../api/channels'
import {
  emptyEditForm,
  useChannelCrud,
  type ChannelEditForm,
} from '../../composables/useChannelCrud'
import { btnPrimaryClass, inputClass, labelClass, selectClass } from '../../lib/cockpit-ui'
import { durationSecondOptions } from '../../lib/target-duration'
import { videoLanguageOptions } from '../../lib/video-languages'
import { useChannelsStore } from '../../stores/channels'
import { useUiStore } from '../../stores/ui'
import { X } from '../../lib/cockpit-icons'

const props = defineProps<{
  open: boolean
  mode: 'create' | 'edit'
  slug?: string | null
}>()

const emit = defineEmits<{
  close: []
  saved: []
}>()

const uiStore = useUiStore()
const channelsStore = useChannelsStore()
const {
  saving,
  uploadingAvatar,
  errorMessage,
  avatarCacheBust,
  loadEditForm,
  createChannel,
  updateChannel,
  uploadAvatar,
} = useChannelCrud()

const newChannel = ref({ slug: '', name: '', niche: '' })
const editForm = ref<ChannelEditForm>(emptyEditForm())
const durationOptions = durationSecondOptions()

const maxDurationOptions = computed(() =>
  durationOptions.filter((seconds) => seconds >= editForm.value.target_duration_min),
)

const languageOptions = computed(() => videoLanguageOptions(editForm.value.video_language))

const channel = computed(() =>
  props.slug ? channelsStore.channels.find((c) => c.slug === props.slug) ?? null : null,
)

const title = computed(() =>
  props.mode === 'create'
    ? uiStore.tr('Cockpit Channel New')
    : `${uiStore.tr('Cockpit Channel Edit')} — ${channel.value?.name ?? props.slug}`,
)

watch(
  () => [props.open, props.mode, props.slug] as const,
  async ([open, mode, slug]) => {
    if (!open) return
    errorMessage.value = null
    if (mode === 'create') {
      newChannel.value = { slug: '', name: '', niche: '' }
      return
    }
    if (slug) {
      editForm.value = await loadEditForm(slug)
    }
  },
)

watch(
  () => editForm.value.target_duration_min,
  (min) => {
    if (editForm.value.target_duration_max < min) {
      editForm.value.target_duration_max = min
    }
  },
)

function close() {
  emit('close')
}

async function submitCreate() {
  await createChannel({ ...newChannel.value })
  emit('saved')
  close()
}

async function submitEdit() {
  if (!props.slug) return
  await updateChannel(props.slug, { ...editForm.value })
  emit('saved')
  close()
}

async function onAvatarChange(event: Event) {
  if (!props.slug) return
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  await uploadAvatar(props.slug, file)
}

function avatarFor(ch: ChannelSummary) {
  return channelAvatarSrc(ch, avatarCacheBust.value)
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
        class="fixed inset-0 z-[100] flex items-start justify-center overflow-y-auto bg-black/60 p-4 sm:items-center light:bg-slate-900/40"
      @click.self="close"
    >
      <section
        class="my-4 w-full max-w-2xl rounded-xl border border-indigo-400/25 bg-cockpit-surface p-5 shadow-2xl shadow-black/50 light:border-slate-200 light:bg-white light:shadow-slate-300/50"
        role="dialog"
        aria-modal="true"
      >
        <div class="mb-4 flex items-center justify-between gap-3">
          <h3 class="cockpit-title text-sm font-bold">{{ title }}</h3>
          <button
            type="button"
            class="grid size-8 place-items-center rounded-lg text-slate-500 hover:bg-slate-800 light:hover:bg-slate-100"
            @click="close"
          >
            <X :size="18" />
          </button>
        </div>

        <template v-if="mode === 'create'">
          <div class="grid gap-3 sm:grid-cols-2">
            <label class="flex flex-col gap-1.5">
              <span :class="labelClass">{{ uiStore.tr('Cockpit Channel Slug') }}</span>
              <input v-model="newChannel.slug" :class="inputClass" placeholder="japao" />
            </label>
            <label class="flex flex-col gap-1.5">
              <span :class="labelClass">{{ uiStore.tr('Cockpit Channel Name') }}</span>
              <input v-model="newChannel.name" :class="inputClass" placeholder="Curiosidades do Japão" />
            </label>
            <label class="flex flex-col gap-1.5 sm:col-span-2">
              <span :class="labelClass">{{ uiStore.tr('Cockpit Channel Niche') }}</span>
              <input v-model="newChannel.niche" :class="inputClass" />
            </label>
          </div>
          <div class="mt-5 flex flex-wrap gap-2">
            <button :class="btnPrimaryClass" type="button" :disabled="saving" @click="submitCreate">
              {{ saving ? uiStore.tr('Cockpit Saving') : uiStore.tr('Cockpit Channel Create') }}
            </button>
            <button
              type="button"
              class="rounded-lg border border-slate-600/30 px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-800 light:border-slate-300 light:text-slate-700 light:hover:bg-slate-100"
              @click="close"
            >
              {{ uiStore.tr('Cockpit Cancel') }}
            </button>
          </div>
        </template>

        <template v-else-if="channel && slug">
          <div class="mb-5 flex flex-wrap items-center gap-4">
            <div
              class="grid size-20 place-items-center overflow-hidden rounded-full bg-slate-800 ring-2 ring-slate-700/60"
            >
              <img
                v-if="avatarFor(channel)"
                :src="avatarFor(channel)!"
                :alt="channel.name"
                class="size-full object-cover"
              />
              <span v-else class="text-2xl font-bold text-slate-300">
                {{ channel.name.trim().charAt(0).toUpperCase() }}
              </span>
            </div>
            <label class="flex flex-col gap-1.5">
              <span :class="labelClass">{{ uiStore.tr('Cockpit Channel Avatar') }}</span>
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                class="max-w-xs text-sm text-slate-400 file:mr-3 file:rounded-lg file:border-0 file:bg-indigo-500/20 file:px-3 file:py-2 file:text-indigo-200"
                :disabled="uploadingAvatar"
                @change="onAvatarChange"
              />
            </label>
          </div>

          <div class="grid gap-3 sm:grid-cols-2">
            <label class="flex flex-col gap-1.5">
              <span :class="labelClass">{{ uiStore.tr('Cockpit Channel Name') }}</span>
              <input v-model="editForm.name" :class="inputClass" />
            </label>
            <label class="flex flex-col gap-1.5">
              <span :class="labelClass">{{ uiStore.tr('Cockpit Channel Niche') }}</span>
              <input v-model="editForm.niche" :class="inputClass" />
            </label>
            <label class="flex flex-col gap-1.5">
              <span :class="labelClass">{{ uiStore.tr('Cockpit Channel Videos Per Day') }}</span>
              <input v-model.number="editForm.videos_per_day" type="number" min="1" :class="inputClass" />
            </label>
            <label class="flex flex-col gap-1.5">
              <span :class="labelClass">{{ uiStore.tr('Cockpit Channel Mode') }}</span>
              <select v-model="editForm.mode" :class="selectClass">
                <option value="faceless">Faceless</option>
                <option value="talking_head">Talking head</option>
              </select>
            </label>
            <label class="flex flex-col gap-1.5">
              <span :class="labelClass">{{ uiStore.tr('Cockpit Video Source') }}</span>
              <select v-model="editForm.video_source" :class="selectClass">
                <option value="collector">{{ uiStore.tr('Collector (local cache)') }}</option>
                <option value="pexels">Pexels</option>
                <option value="pixabay">Pixabay</option>
                <option value="local">Local</option>
              </select>
            </label>
            <label class="flex flex-col gap-1.5">
              <span :class="labelClass">{{ uiStore.tr('Cockpit Video Aspect') }}</span>
              <select v-model="editForm.video_aspect" :class="selectClass">
                <option value="9:16">9:16</option>
                <option value="16:9">16:9</option>
                <option value="1:1">1:1</option>
              </select>
            </label>
            <div class="flex flex-col gap-1.5 sm:col-span-2">
              <span :class="labelClass">{{ uiStore.tr('Cockpit Target Duration') }}</span>
              <div class="flex items-center gap-2">
                <select v-model.number="editForm.target_duration_min" :class="[selectClass, 'min-w-0 flex-1']">
                  <option v-for="seconds in durationOptions" :key="`min-${seconds}`" :value="seconds">
                    {{ seconds }}s
                  </option>
                </select>
                <span class="cockpit-muted shrink-0 text-sm">–</span>
                <select v-model.number="editForm.target_duration_max" :class="[selectClass, 'min-w-0 flex-1']">
                  <option v-for="seconds in maxDurationOptions" :key="`max-${seconds}`" :value="seconds">
                    {{ seconds }}s
                  </option>
                </select>
              </div>
            </div>
            <label class="flex flex-col gap-1.5">
              <span :class="labelClass">{{ uiStore.tr('Cockpit Channel Language') }}</span>
              <select v-model="editForm.video_language" :class="selectClass">
                <option
                  v-for="option in languageOptions"
                  :key="option.value || 'auto'"
                  :value="option.value"
                >
                  {{ option.value === '' ? uiStore.tr('Auto Detect') : option.label }}
                </option>
              </select>
            </label>
          </div>

          <div class="mt-5 flex flex-wrap gap-2">
            <button :class="btnPrimaryClass" type="button" :disabled="saving" @click="submitEdit">
              {{ saving ? uiStore.tr('Cockpit Saving') : uiStore.tr('Cockpit Save') }}
            </button>
            <button
              type="button"
              class="rounded-lg border border-slate-600/30 px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-800 light:border-slate-300 light:text-slate-700 light:hover:bg-slate-100"
              @click="close"
            >
              {{ uiStore.tr('Cockpit Cancel') }}
            </button>
          </div>
        </template>

        <p v-if="errorMessage" class="mt-4 text-sm text-rose-400">{{ errorMessage }}</p>
      </section>
    </div>
  </Teleport>
</template>
