import { api } from './client'
import type { Workspace } from '../types/workspace'

export interface ChannelSummary {
  slug: string
  name: string
  niche: string
  mode: string
  video_source: string
  avatar_url?: string | null
  videos_per_day?: number
}

export interface ChannelCreateBody {
  slug: string
  name: string
  niche?: string
}

export interface ChannelUpdateBody {
  name?: string
  niche?: string
  videos_per_day?: number
  mode?: string
  video_source?: string
  video_aspect?: string
  target_duration?: string
  video_language?: string
}

export interface ChannelConfigResponse {
  slug: string
  config: Record<string, unknown>
  runtime: Record<string, unknown>
}

export interface Topic {
  uid: string
  id: number
  category: string
  topic: string
  topic_hash: string
  music_profiles: string[]
  status: string
  generated_at: string | null
  task_id: string | null
  video_path: string | null
  approved: boolean
}

export const channelsApi = {
  list: () => api.get<{ channels: ChannelSummary[] }>('/api/v1/channels'),

  create: (body: ChannelCreateBody) => api.post<ChannelSummary>('/api/v1/channels', body),

  update: (slug: string, body: ChannelUpdateBody) =>
    api.put<ChannelSummary>(`/api/v1/channels/${slug}`, body),

  delete: (slug: string) => api.delete<{ deleted: boolean; slug: string }>(`/api/v1/channels/${slug}`),

  uploadAvatar: (slug: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.upload<{ slug: string; avatar_url: string }>(`/api/v1/channels/${slug}/avatar`, form)
  },

  get: (slug: string) => api.get<ChannelConfigResponse>(`/api/v1/channels/${slug}`),

  listTopics: (slug: string, status?: string) =>
    api.get<{ topics: Topic[]; counts: Record<string, number> }>(`/api/v1/channels/${slug}/topics`, { status }),

  loadTopicIntoWorkspace: (slug: string, topicUid: string) =>
    api.post<{ workspace: Workspace; topic: Topic }>(
      `/api/v1/channels/${slug}/topics/${topicUid}/load-into-workspace`,
    ),

  updateTopicStatus: (
    slug: string,
    topicUid: string,
    body: { status: string; task_id?: string; video_path?: string; approved?: boolean },
  ) => api.patch<Topic>(`/api/v1/channels/${slug}/topics/${topicUid}`, body),
}

export function channelAvatarSrc(channel: ChannelSummary, cacheBust?: number): string | null {
  if (!channel.avatar_url) return null
  const suffix = cacheBust ? `?v=${cacheBust}` : ''
  return `${channel.avatar_url}${suffix}`
}
