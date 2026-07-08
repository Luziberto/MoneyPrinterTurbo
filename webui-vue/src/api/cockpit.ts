import { api } from './client'
import type { StepState, Workspace, WorkspacePatchBody } from '../types/workspace'

export interface WorkspaceSteps {
  states: StepState[]
  step_ids: string[]
  blockers: { provider: string; detail: string }[]
}

export interface ProviderReadiness {
  status: 'ready' | 'blocked' | 'skipped'
  detail: string
}

export type ProvidersResponse = Record<'llm' | 'collector' | 'tts' | 'ffmpeg' | 'bgm', ProviderReadiness>

export interface RuntimeLimits {
  max_threads: number
  max_remote_video_mb: number
  max_downloads_per_task: number
  generation_lock_ttl_seconds: number
  low_memory_mode: boolean
  lock: { status: string; task_id: string; owner?: string; created_at_epoch?: number } | null
}

export const cockpitApi = {
  getWorkspace: (channelSlug: string | null) =>
    api.get<Workspace>('/api/v1/cockpit/workspace', { channel_slug: channelSlug ?? undefined }),

  patchWorkspace: (channelSlug: string | null, patch: WorkspacePatchBody) =>
    api.patch<Workspace>('/api/v1/cockpit/workspace', patch, { channel_slug: channelSlug ?? undefined }),

  resetWorkspace: (channelSlug: string) =>
    api.post<Workspace>('/api/v1/cockpit/workspace/reset', {}, { channel_slug: channelSlug }),

  restoreField: (channelSlug: string, fieldKey: string) =>
    api.post<Workspace>(
      '/api/v1/cockpit/workspace/restore-field',
      { field_key: fieldKey },
      { channel_slug: channelSlug },
    ),

  getSteps: (channelSlug: string | null) =>
    api.get<WorkspaceSteps>('/api/v1/cockpit/workspace/steps', { channel_slug: channelSlug ?? undefined }),

  runPreview: (channelSlug: string | null, includeAudio: boolean) =>
    api.post<Workspace & { preview_audio_url?: string }>(
      '/api/v1/cockpit/preview',
      { include_audio: includeAudio },
      { channel_slug: channelSlug ?? undefined },
    ),

  getProviders: (videoSource: string, voiceName: string) =>
    api.get<ProvidersResponse>('/api/v1/cockpit/providers', { video_source: videoSource, voice_name: voiceName }),

  getRuntimeLimits: () => api.get<RuntimeLimits>('/api/v1/cockpit/runtime-limits'),

  clearGenerationLock: (force: boolean) =>
    api.post<{ cleared: boolean }>('/api/v1/cockpit/runtime-limits/clear-lock', { force }),
}
