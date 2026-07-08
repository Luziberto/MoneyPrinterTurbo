import { api } from './client'
import type { CollectorJobSnapshot, CollectorKeyword } from '../types/workspace'

export const collectorApi = {
  health: () => api.get<{ healthy: boolean }>('/api/v1/collector/health'),

  dashboard: () => api.get<Record<string, unknown>>('/api/v1/collector/dashboard'),

  search: (query: string, limit?: number) =>
    api.get<{ hits: Record<string, unknown>[] }>('/api/v1/collector/search', { query, limit }),

  createJob: (keywords: CollectorKeyword[], targetClips: number, minAcceptableClips: number, channelSlug?: string) =>
    api.post<CollectorJobSnapshot>('/api/v1/collector/jobs', {
      keywords,
      target_clips: targetClips,
      min_acceptable_clips: minAcceptableClips,
      channel_slug: channelSlug,
    }),

  getJob: (jobId: string, channelSlug?: string) =>
    api.get<CollectorJobSnapshot>(`/api/v1/collector/jobs/${jobId}`, { channel_slug: channelSlug }),
}
