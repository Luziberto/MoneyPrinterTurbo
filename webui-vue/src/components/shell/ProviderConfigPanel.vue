<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { X } from '@lucide/vue'
import { configApi, type ConfigSnapshot } from '../../api/config'
import { PROVIDER_LABEL_KEYS, useDashboardStore } from '../../stores/dashboard'
import { useUiStore } from '../../stores/ui'
import { useWorkspaceStore } from '../../stores/workspace'
import { inputClass, labelClass, selectClass } from '../../lib/cockpit-ui'
import { PROVIDER_ICON_COMPONENTS } from '../../lib/cockpit-icons'

const uiStore = useUiStore()
const workspaceStore = useWorkspaceStore()
const dashboardStore = useDashboardStore()

const appConfig = ref<ConfigSnapshot | null>(null)
const saving = ref(false)

const activeKey = computed(() => dashboardStore.selectedProvider)

const panelTitle = computed(() => {
  if (!activeKey.value) return ''
  return uiStore.tr(PROVIDER_LABEL_KEYS[activeKey.value])
})

const panelIcon = computed(() => (activeKey.value ? PROVIDER_ICON_COMPONENTS[activeKey.value] : null))

const llmProvider = computed(() => String(appConfig.value?.app.llm_provider ?? '').trim())

const llmApiKeyField = computed(() => (llmProvider.value ? `${llmProvider.value}_api_key` : ''))

const showStockKeys = computed(() => {
  const source = workspaceStore.workspace?.media.video_source
  return source === 'pexels' || source === 'pixabay' || source === 'collector'
})

async function loadAppConfig() {
  appConfig.value = await configApi.get()
}

onMounted(() => {
  void loadAppConfig()
})

watch(activeKey, (key) => {
  if (key) void loadAppConfig()
})

async function patchWorkspace(body: Parameters<typeof workspaceStore.patch>[0]) {
  await workspaceStore.patch(body)
  await dashboardStore.refresh()
}

async function saveAppField(section: keyof ConfigSnapshot, key: string, value: string) {
  if (!appConfig.value) return
  appConfig.value[section][key] = value
  saving.value = true
  try {
    appConfig.value = await configApi.put({ [section]: { [key]: value } })
    await dashboardStore.refresh()
  } finally {
    saving.value = false
  }
}

function onVideoSourceChange(event: Event) {
  void patchWorkspace({ media: { video_source: (event.target as HTMLSelectElement).value } })
}

function onTargetClipsChange(event: Event) {
  void patchWorkspace({
    media: { collector_target_clips: Number((event.target as HTMLInputElement).value) },
  })
}

function onMinClipsChange(event: Event) {
  void patchWorkspace({
    media: { collector_min_acceptable_clips: Number((event.target as HTMLInputElement).value) },
  })
}

function onCollectorUrlChange(event: Event) {
  void saveAppField('app', 'collector_base_url', (event.target as HTMLInputElement).value)
}

function onLlmProviderChange(event: Event) {
  void saveAppField('app', 'llm_provider', (event.target as HTMLInputElement).value)
}

function onLlmApiKeyChange(event: Event) {
  if (!llmApiKeyField.value) return
  void saveAppField('app', llmApiKeyField.value, (event.target as HTMLInputElement).value)
}

function onPexelsKeysChange(event: Event) {
  void saveAppField('app', 'pexels_api_keys', (event.target as HTMLInputElement).value)
}

function onPixabayKeysChange(event: Event) {
  void saveAppField('app', 'pixabay_api_keys', (event.target as HTMLInputElement).value)
}

function onTtsServerChange(event: Event) {
  void patchWorkspace({ voice: { tts_server: (event.target as HTMLSelectElement).value } })
}

function onVoiceNameChange(event: Event) {
  void patchWorkspace({ voice: { voice_name: (event.target as HTMLInputElement).value } })
}

function onVoiceVolumeChange(event: Event) {
  void patchWorkspace({
    voice: { voice_volume: Number((event.target as HTMLInputElement).value) },
  })
}

function onVoiceRateChange(event: Event) {
  void patchWorkspace({
    voice: { voice_rate: Number((event.target as HTMLInputElement).value) },
  })
}

function onVideoAspectChange(event: Event) {
  void patchWorkspace({ media: { video_aspect: (event.target as HTMLSelectElement).value } })
}

function onConcatModeChange(event: Event) {
  void patchWorkspace({
    media: { video_concat_mode: (event.target as HTMLSelectElement).value },
  })
}

function onClipDurationChange(event: Event) {
  void patchWorkspace({
    media: { video_clip_duration: Number((event.target as HTMLInputElement).value) },
  })
}

function onTransitionChange(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  void patchWorkspace({ media: { video_transition_mode: value || null } })
}

function onBgmTypeChange(event: Event) {
  void patchWorkspace({ bgm: { bgm_type: (event.target as HTMLSelectElement).value } })
}

function onBgmProfileChange(event: Event) {
  void patchWorkspace({ bgm: { bgm_profile: (event.target as HTMLInputElement).value } })
}

function onBgmVolumeChange(event: Event) {
  void patchWorkspace({
    bgm: { bgm_volume: Number((event.target as HTMLInputElement).value) },
  })
}
</script>

<template>
  <section
    v-if="activeKey && workspaceStore.workspace"
    class="rounded-xl border border-indigo-400/25 bg-cockpit-surface/90 p-4 shadow-lg shadow-black/20 light:border-indigo-300/40 light:bg-white light:shadow-slate-200/60"
  >
    <div class="mb-4 flex items-center justify-between gap-3">
      <div class="flex items-center gap-2.5">
        <div
          v-if="panelIcon"
          class="grid size-9 place-items-center rounded-lg bg-indigo-500/15 text-indigo-300"
        >
          <component :is="panelIcon" :size="18" :stroke-width="2" />
        </div>
        <div>
          <h3 class="cockpit-title text-sm font-bold">
            {{ uiStore.tr('Cockpit Provider Config Title') }} — {{ panelTitle }}
          </h3>
          <p class="text-xs text-slate-500">
            {{ dashboardStore.providers?.[activeKey]?.detail }}
          </p>
        </div>
      </div>
      <button
        type="button"
        class="grid size-8 place-items-center rounded-lg text-slate-500 transition hover:bg-slate-800 hover:text-slate-200 light:hover:bg-slate-100 light:hover:text-slate-700"
        aria-label="Fechar"
        @click="dashboardStore.closeProvider()"
      >
        <X :size="18" />
      </button>
    </div>

    <div v-if="activeKey === 'collector'" class="grid gap-3 sm:grid-cols-2">
      <label class="flex flex-col gap-1.5 sm:col-span-2">
        <span :class="labelClass">{{ uiStore.tr('Cockpit Video Source') }}</span>
        <select
          :class="selectClass"
          :value="workspaceStore.workspace.media.video_source"
          @change="onVideoSourceChange"
        >
          <option value="collector">{{ uiStore.tr('Collector (local cache)') }}</option>
          <option value="pexels">Pexels</option>
          <option value="pixabay">Pixabay</option>
          <option value="local">Local</option>
        </select>
      </label>
      <label class="flex flex-col gap-1.5">
        <span :class="labelClass">{{ uiStore.tr('Cockpit Target Clips') }}</span>
        <input
          type="number"
          min="1"
          :class="inputClass"
          :value="workspaceStore.workspace.media.collector_target_clips ?? 25"
          @change="onTargetClipsChange"
        />
      </label>
      <label class="flex flex-col gap-1.5">
        <span :class="labelClass">{{ uiStore.tr('Cockpit Min Clips') }}</span>
        <input
          type="number"
          min="1"
          :class="inputClass"
          :value="workspaceStore.workspace.media.collector_min_acceptable_clips ?? 20"
          @change="onMinClipsChange"
        />
      </label>
      <label v-if="appConfig" class="flex flex-col gap-1.5 sm:col-span-2">
        <span :class="labelClass">{{ uiStore.tr('Cockpit Collector Base URL') }}</span>
        <input
          type="url"
          :class="inputClass"
          :value="String(appConfig.app.collector_base_url ?? '')"
          :disabled="saving"
          @change="onCollectorUrlChange"
        />
      </label>
      <template v-if="appConfig && showStockKeys">
        <label class="flex flex-col gap-1.5 sm:col-span-2">
          <span :class="labelClass">{{ uiStore.tr('Cockpit Pexels API Keys') }}</span>
          <input
            type="password"
            :class="inputClass"
            :value="String(appConfig.app.pexels_api_keys ?? '')"
            :disabled="saving"
            @change="onPexelsKeysChange"
          />
        </label>
        <label class="flex flex-col gap-1.5 sm:col-span-2">
          <span :class="labelClass">{{ uiStore.tr('Cockpit Pixabay API Keys') }}</span>
          <input
            type="password"
            :class="inputClass"
            :value="String(appConfig.app.pixabay_api_keys ?? '')"
            :disabled="saving"
            @change="onPixabayKeysChange"
          />
        </label>
      </template>
    </div>

    <div v-else-if="activeKey === 'llm'" class="grid gap-3 sm:grid-cols-2">
      <label v-if="appConfig" class="flex flex-col gap-1.5">
        <span :class="labelClass">{{ uiStore.tr('Cockpit LLM Provider') }}</span>
        <input
          :class="inputClass"
          :value="llmProvider"
          :disabled="saving"
          @change="onLlmProviderChange"
        />
      </label>
      <label v-if="appConfig && llmApiKeyField" class="flex flex-col gap-1.5">
        <span :class="labelClass">{{ uiStore.tr('Cockpit LLM API Key') }}</span>
        <input
          type="password"
          :class="inputClass"
          :value="String(appConfig.app[llmApiKeyField] ?? '')"
          :disabled="saving"
          @change="onLlmApiKeyChange"
        />
      </label>
    </div>

    <div v-else-if="activeKey === 'tts'" class="grid gap-3 sm:grid-cols-2">
      <label class="flex flex-col gap-1.5">
        <span :class="labelClass">{{ uiStore.tr('Cockpit TTS Server') }}</span>
        <select
          :class="selectClass"
          :value="workspaceStore.workspace.voice.tts_server"
          @change="onTtsServerChange"
        >
          <option value="azure-tts-v1">Azure TTS V1</option>
          <option value="azure-tts-v2">Azure TTS V2</option>
          <option value="siliconflow">SiliconFlow</option>
          <option value="gemini-tts">Gemini TTS</option>
          <option value="mimo-tts">MiMo TTS</option>
          <option value="elevenlabs">ElevenLabs</option>
          <option value="chatterbox">Chatterbox</option>
        </select>
      </label>
      <label class="flex flex-col gap-1.5">
        <span :class="labelClass">{{ uiStore.tr('Cockpit Voice Name') }}</span>
        <input
          :class="inputClass"
          :value="workspaceStore.workspace.voice.voice_name"
          @change="onVoiceNameChange"
        />
      </label>
      <label class="flex flex-col gap-1.5">
        <span :class="labelClass">{{ uiStore.tr('Cockpit Voice Volume') }}</span>
        <input
          type="number"
          min="0"
          max="2"
          step="0.05"
          :class="inputClass"
          :value="workspaceStore.workspace.voice.voice_volume"
          @change="onVoiceVolumeChange"
        />
      </label>
      <label class="flex flex-col gap-1.5">
        <span :class="labelClass">{{ uiStore.tr('Cockpit Voice Rate') }}</span>
        <input
          type="number"
          min="0.5"
          max="2"
          step="0.05"
          :class="inputClass"
          :value="workspaceStore.workspace.voice.voice_rate"
          @change="onVoiceRateChange"
        />
      </label>
    </div>

    <div v-else-if="activeKey === 'ffmpeg'" class="grid gap-3 sm:grid-cols-2">
      <label class="flex flex-col gap-1.5">
        <span :class="labelClass">{{ uiStore.tr('Cockpit Video Aspect') }}</span>
        <select
          :class="selectClass"
          :value="workspaceStore.workspace.media.video_aspect"
          @change="onVideoAspectChange"
        >
          <option value="9:16">9:16</option>
          <option value="16:9">16:9</option>
          <option value="1:1">1:1</option>
        </select>
      </label>
      <label class="flex flex-col gap-1.5">
        <span :class="labelClass">{{ uiStore.tr('Cockpit Video Concat Mode') }}</span>
        <select
          :class="selectClass"
          :value="workspaceStore.workspace.media.video_concat_mode"
          @change="onConcatModeChange"
        >
          <option value="random">Random</option>
          <option value="sequential">Sequential</option>
        </select>
      </label>
      <label class="flex flex-col gap-1.5">
        <span :class="labelClass">{{ uiStore.tr('Cockpit Video Clip Duration') }}</span>
        <input
          type="number"
          min="1"
          max="30"
          :class="inputClass"
          :value="workspaceStore.workspace.media.video_clip_duration"
          @change="onClipDurationChange"
        />
      </label>
      <label class="flex flex-col gap-1.5">
        <span :class="labelClass">{{ uiStore.tr('Cockpit Video Transition') }}</span>
        <select
          :class="selectClass"
          :value="workspaceStore.workspace.media.video_transition_mode ?? ''"
          @change="onTransitionChange"
        >
          <option value="">None</option>
          <option value="shuffle">Shuffle</option>
          <option value="fade_in">Fade in</option>
          <option value="fade_out">Fade out</option>
          <option value="slide_in">Slide in</option>
          <option value="slide_out">Slide out</option>
        </select>
      </label>
    </div>

    <div v-else-if="activeKey === 'bgm'" class="grid gap-3 sm:grid-cols-2">
      <label class="flex flex-col gap-1.5">
        <span :class="labelClass">{{ uiStore.tr('Cockpit BGM Type') }}</span>
        <select
          :class="selectClass"
          :value="workspaceStore.workspace.bgm.bgm_type"
          @change="onBgmTypeChange"
        >
          <option value="random">Random</option>
          <option value="profile_random">Profile random</option>
          <option value="custom">Custom</option>
        </select>
      </label>
      <label class="flex flex-col gap-1.5">
        <span :class="labelClass">{{ uiStore.tr('Cockpit BGM Profile') }}</span>
        <input
          :class="inputClass"
          :value="workspaceStore.workspace.bgm.bgm_profile"
          @change="onBgmProfileChange"
        />
      </label>
      <label class="flex flex-col gap-1.5">
        <span :class="labelClass">{{ uiStore.tr('Cockpit BGM Volume') }}</span>
        <input
          type="number"
          min="0"
          max="1"
          step="0.05"
          :class="inputClass"
          :value="workspaceStore.workspace.bgm.bgm_volume"
          @change="onBgmVolumeChange"
        />
      </label>
    </div>
  </section>
</template>
