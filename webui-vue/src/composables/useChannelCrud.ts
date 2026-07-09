import { ref } from 'vue'
import { channelsApi, type ChannelCreateBody, type ChannelUpdateBody } from '../api/channels'
import { ApiError } from '../api/client'
import { useChannelsStore } from '../stores/channels'
import { useDashboardStore } from '../stores/dashboard'
import { useWorkspaceStore } from '../stores/workspace'

export interface ChannelEditForm {
  name: string
  niche: string
  videos_per_day: number
  mode: string
  video_source: string
  video_aspect: string
  target_duration: string
  video_language: string
}

export function emptyEditForm(): ChannelEditForm {
  return {
    name: '',
    niche: '',
    videos_per_day: 1,
    mode: 'faceless',
    video_source: 'collector',
    video_aspect: '9:16',
    target_duration: '60-90',
    video_language: 'pt-BR',
  }
}

export function useChannelCrud() {
  const channelsStore = useChannelsStore()
  const workspaceStore = useWorkspaceStore()
  const dashboardStore = useDashboardStore()

  const saving = ref(false)
  const deleting = ref(false)
  const uploadingAvatar = ref(false)
  const errorMessage = ref<string | null>(null)
  const avatarCacheBust = ref(0)

  async function refreshAll() {
    await channelsStore.fetchChannels()
    if (!channelsStore.activeSlug && channelsStore.channels[0]) {
      channelsStore.setActiveChannel(channelsStore.channels[0].slug)
    }
    if (channelsStore.activeSlug) {
      await workspaceStore.load(channelsStore.activeSlug)
    } else {
      workspaceStore.channelSlug = null
      workspaceStore.workspace = null
      workspaceStore.steps = null
    }
    await dashboardStore.refresh()
  }

  async function loadEditForm(slug: string): Promise<ChannelEditForm> {
    const detail = await channelsApi.get(slug)
    const config = detail.config
    return {
      name: String(config.name ?? ''),
      niche: String(config.niche ?? ''),
      videos_per_day: Number(config.videos_per_day ?? 1),
      mode: String(config.mode ?? 'faceless'),
      video_source: String(config.video_source ?? 'collector'),
      video_aspect: String(config.video_aspect ?? '9:16'),
      target_duration: String(config.target_duration ?? '60-90'),
      video_language: String(config.video_language ?? 'pt-BR'),
    }
  }

  async function createChannel(body: ChannelCreateBody) {
    errorMessage.value = null
    saving.value = true
    try {
      const created = await channelsApi.create({
        slug: body.slug.trim().toLowerCase(),
        name: body.name.trim(),
        niche: body.niche?.trim() ?? '',
      })
      channelsStore.setActiveChannel(created.slug)
      await refreshAll()
      return created
    } catch (err) {
      errorMessage.value = err instanceof ApiError ? err.message : String(err)
      throw err
    } finally {
      saving.value = false
    }
  }

  async function updateChannel(slug: string, body: ChannelUpdateBody) {
    errorMessage.value = null
    saving.value = true
    try {
      await channelsApi.update(slug, body)
      await refreshAll()
    } catch (err) {
      errorMessage.value = err instanceof ApiError ? err.message : String(err)
      throw err
    } finally {
      saving.value = false
    }
  }

  async function deleteChannel(slug: string) {
    errorMessage.value = null
    deleting.value = true
    try {
      await channelsApi.delete(slug)
      if (channelsStore.activeSlug === slug) {
        const next = channelsStore.channels.find((c) => c.slug !== slug)
        channelsStore.setActiveChannel(next?.slug ?? '')
      }
      await refreshAll()
    } catch (err) {
      errorMessage.value = err instanceof ApiError ? err.message : String(err)
      throw err
    } finally {
      deleting.value = false
    }
  }

  async function uploadAvatar(slug: string, file: File) {
    uploadingAvatar.value = true
    errorMessage.value = null
    try {
      await channelsApi.uploadAvatar(slug, file)
      avatarCacheBust.value = Date.now()
      await channelsStore.fetchChannels()
    } catch (err) {
      errorMessage.value = err instanceof ApiError ? err.message : String(err)
      throw err
    } finally {
      uploadingAvatar.value = false
    }
  }

  return {
    saving,
    deleting,
    uploadingAvatar,
    errorMessage,
    avatarCacheBust,
    refreshAll,
    loadEditForm,
    createChannel,
    updateChannel,
    deleteChannel,
    uploadAvatar,
  }
}
