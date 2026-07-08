import { defineStore } from 'pinia'
import { cockpitApi, type WorkspaceSteps } from '../api/cockpit'
import type { Workspace, WorkspacePatchBody } from '../types/workspace'
import { ApiError } from '../api/client'

interface State {
  channelSlug: string | null
  workspace: Workspace | null
  steps: WorkspaceSteps | null
  previewAudioUrl: string | null
  loading: boolean
  error: string | null
}

export const useWorkspaceStore = defineStore('workspace', {
  state: (): State => ({
    channelSlug: null,
    workspace: null,
    steps: null,
    previewAudioUrl: null,
    loading: false,
    error: null,
  }),

  actions: {
    async load(channelSlug: string | null) {
      this.loading = true
      this.error = null
      try {
        this.channelSlug = channelSlug
        this.workspace = await cockpitApi.getWorkspace(channelSlug)
        await this.refreshSteps()
      } catch (err) {
        this.error = err instanceof ApiError ? err.message : String(err)
      } finally {
        this.loading = false
      }
    },

    async refreshSteps() {
      this.steps = await cockpitApi.getSteps(this.channelSlug)
    },

    async patch(body: WorkspacePatchBody) {
      this.workspace = await cockpitApi.patchWorkspace(this.channelSlug, body)
      await this.refreshSteps()
      return this.workspace
    },

    async reset() {
      if (!this.channelSlug) return
      this.workspace = await cockpitApi.resetWorkspace(this.channelSlug)
      await this.refreshSteps()
    },

    async restoreField(fieldKey: string) {
      if (!this.channelSlug) return
      this.workspace = await cockpitApi.restoreField(this.channelSlug, fieldKey)
      await this.refreshSteps()
    },

    async runPreview(includeAudio: boolean) {
      this.loading = true
      this.error = null
      try {
        const result = await cockpitApi.runPreview(this.channelSlug, includeAudio)
        const { preview_audio_url, ...workspace } = result
        this.workspace = workspace
        this.previewAudioUrl = preview_audio_url ?? null
        await this.refreshSteps()
      } catch (err) {
        this.error = err instanceof ApiError ? err.message : String(err)
        throw err
      } finally {
        this.loading = false
      }
    },

    setActiveStep(step: number) {
      void this.patch({ active_step: step })
    },
  },
})
