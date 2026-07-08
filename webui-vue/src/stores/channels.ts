import { defineStore } from 'pinia'
import { channelsApi, type ChannelSummary } from '../api/channels'

interface State {
  channels: ChannelSummary[]
  activeSlug: string | null
  loading: boolean
}

export const useChannelsStore = defineStore('channels', {
  state: (): State => ({
    channels: [],
    activeSlug: null,
    loading: false,
  }),

  actions: {
    async fetchChannels() {
      this.loading = true
      try {
        const { channels } = await channelsApi.list()
        this.channels = channels
        if (!this.activeSlug && channels.length > 0) {
          this.activeSlug = channels[0].slug
        }
      } finally {
        this.loading = false
      }
    },

    setActiveChannel(slug: string) {
      this.activeSlug = slug
    },
  },
})
