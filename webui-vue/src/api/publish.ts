import { api } from './client'

export interface PublishStatus {
  backend: string
  configured: boolean
  platforms: string[]
  auto_upload: boolean
  youtube_privacy_status: string
}

export const publishApi = {
  getStatus: () => api.get<PublishStatus>('/api/v1/publish/status'),

  publish: (
    channelSlug: string | null,
    body: {
      video_paths: string[]
      subject: string
      script?: string
      language?: string
      platforms?: string[]
      youtube_privacy_status?: string
    },
  ) => api.post<{ results: Record<string, unknown>[] }>('/api/v1/publish', body, { channel_slug: channelSlug ?? undefined }),
}
