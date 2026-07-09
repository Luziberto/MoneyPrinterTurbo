import { defineStore } from 'pinia'
import { channelsApi } from '../api/channels'
import { cockpitApi, type ProvidersResponse } from '../api/cockpit'
import { useChannelsStore } from './channels'
import { useWorkspaceStore } from './workspace'

export const PROVIDER_ORDER = ['llm', 'collector', 'tts', 'ffmpeg', 'bgm'] as const
export type ProviderKey = (typeof PROVIDER_ORDER)[number]

export const PROVIDER_LABEL_KEYS: Record<ProviderKey, string> = {
  collector: 'Cockpit Provider Collector',
  llm: 'Cockpit Provider LLM',
  tts: 'Cockpit Provider TTS',
  ffmpeg: 'Cockpit Provider FFmpeg',
  bgm: 'Cockpit Provider BGM',
}

interface State {
  providers: ProvidersResponse | null
  channelRuntime: Record<string, unknown> | null
  channelConfig: Record<string, unknown> | null
  loading: boolean
  lastFetchedAt: Date | null
  selectedProvider: ProviderKey | null
}

export const useDashboardStore = defineStore('dashboard', {
  state: (): State => ({
    providers: null,
    channelRuntime: null,
    channelConfig: null,
    loading: false,
    lastFetchedAt: null,
    selectedProvider: null,
  }),

  getters: {
    readyCount(state): number {
      if (!state.providers) return 0
      return PROVIDER_ORDER.filter((key) => state.providers![key].status === 'ready').length
    },

    totalProviders(): number {
      return PROVIDER_ORDER.length
    },

    allReady(): boolean {
      return this.readyCount === this.totalProviders
    },
  },

  actions: {
    toggleProvider(key: ProviderKey) {
      this.selectedProvider = this.selectedProvider === key ? null : key
    },

    openProvider(key: ProviderKey) {
      this.selectedProvider = key
    },

    closeProvider() {
      this.selectedProvider = null
    },

    async refresh() {
      const workspaceStore = useWorkspaceStore()
      const channelsStore = useChannelsStore()
      const workspace = workspaceStore.workspace
      if (!workspace) return

      this.loading = true
      try {
        this.providers = await cockpitApi.getProviders(
          workspace.media.video_source,
          workspace.voice.voice_name,
        )
        if (channelsStore.activeSlug) {
          const detail = await channelsApi.get(channelsStore.activeSlug)
          this.channelConfig = detail.config
          this.channelRuntime = detail.runtime
        } else {
          this.channelConfig = null
          this.channelRuntime = null
        }
        this.lastFetchedAt = new Date()
      } finally {
        this.loading = false
      }
    },
  },
})
