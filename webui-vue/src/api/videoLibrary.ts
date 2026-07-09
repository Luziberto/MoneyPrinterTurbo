import { api } from './client'

// Mirrors app/services/video_library_store.py's row shapes and
// app/controllers/v1/videos_library.py's response envelopes.

export const VIDEO_STATUSES = [
  'draft',
  'rendering',
  'ready',
  'scheduled',
  'published',
  'archived',
  'failed',
] as const
export type VideoStatus = (typeof VIDEO_STATUSES)[number]

export const PUBLISH_PLATFORMS = ['tiktok', 'instagram', 'youtube', 'facebook'] as const
export type PublishPlatform = (typeof PUBLISH_PLATFORMS)[number]

export interface VideoRow {
  id: string
  project_id: string | null
  channel_slug: string
  title: string
  subject: string
  keywords: unknown[]
  thumbnail_path: string | null
  video_path: string | null
  duration_seconds: number | null
  file_size_bytes: number | null
  tags: string[]
  caption: string
  status: VideoStatus
  error: string | null
  pipeline_version: string | null
  source: string
  created_at: string
  updated_at: string
}

export interface VideoPublication {
  id: string
  video_id: string
  platform: string
  provider: string
  status: 'scheduled' | 'publishing' | 'published' | 'failed' | 'cancelled'
  scheduled_at: string | null
  published_at: string | null
  url: string | null
  error: string | null
  result: unknown
  created_at: string
  updated_at: string
}

export interface VideoEvent {
  id: string
  video_id: string
  type: string
  actor: string
  created_at: string
  data: Record<string, unknown>
}

export interface VideoAsset {
  kind: string
  name: string
  size_bytes: number
  url: string
}

export interface VideoDetail extends VideoRow {
  script: { script?: string; search_terms?: unknown[]; params?: Record<string, unknown> } | null
  publications: VideoPublication[]
  assets: VideoAsset[]
  events: VideoEvent[]
}

export interface VideoListResult {
  videos: VideoRow[]
  total: number
  page: number
  page_size: number
}

export interface VideoListFilters {
  status?: VideoStatus
  channel_slug?: string
  tag?: string
  date_from?: string
  date_to?: string
  q?: string
  page?: number
  page_size?: number
}

export const videoLibraryApi = {
  list: (filters: VideoListFilters = {}) =>
    api.get<VideoListResult>('/api/v1/video-library', filters as Record<string, string | number>),

  get: (videoId: string) => api.get<VideoDetail>(`/api/v1/video-library/${videoId}`),

  update: (videoId: string, body: { title?: string; tags?: string[]; caption?: string }) =>
    api.patch<VideoRow>(`/api/v1/video-library/${videoId}`, body),

  delete: (videoId: string) => api.delete<{ deleted: boolean }>(`/api/v1/video-library/${videoId}`),

  publish: (videoId: string, platforms: string[], youtubePrivacyStatus?: string) =>
    api.post<{ video: VideoRow; publications: VideoPublication[] }>(
      `/api/v1/video-library/${videoId}/publish`,
      { platforms, youtube_privacy_status: youtubePrivacyStatus },
    ),

  schedule: (videoId: string, platforms: string[], scheduledAt: string) =>
    api.post<{ video: VideoRow; publications: VideoPublication[] }>(
      `/api/v1/video-library/${videoId}/schedule`,
      { platforms, scheduled_at: scheduledAt },
    ),

  cancelPublication: (videoId: string, pubId: string) =>
    api.post<VideoPublication>(`/api/v1/video-library/${videoId}/publications/${pubId}/cancel`),

  archive: (videoId: string) => api.post<VideoRow>(`/api/v1/video-library/${videoId}/archive`),

  restore: (videoId: string) => api.post<VideoRow>(`/api/v1/video-library/${videoId}/restore`),

  reRender: (videoId: string) =>
    api.post<{ task_id: string; request_id: string; params: Record<string, unknown> }>(
      `/api/v1/video-library/${videoId}/re-render`,
    ),
}
