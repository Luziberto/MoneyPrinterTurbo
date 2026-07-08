import { api } from './client'
import type { Workspace } from '../types/workspace'

export interface ChannelSummary {
  slug: string
  name: string
  niche: string
  mode: string
  video_source: string
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
