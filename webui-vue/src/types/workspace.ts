// Mirrors app/models/schema.py's Workspace + nested groups (Python source of
// truth). Keep in sync by hand -- there's no codegen at this surface size.

export interface CollectorKeyword {
  term: string
  weight: number
  visual_intent: string
  alternatives: string[]
  required_concepts: string[]
  optional_concepts: string[]
}

export interface WorkspaceScript {
  video_subject: string
  video_script: string
  script_mode: 'auto' | 'verbatim' | 'polish'
  video_language: string
  paragraph_number: number
  video_script_prompt: string
  use_custom_system_prompt: boolean
  custom_system_prompt: string
  match_materials_to_script: boolean
}

export interface WorkspaceKeywords {
  terms: CollectorKeyword[]
  has_explicit_weights: boolean
}

export interface CollectorSelectedClip {
  path: string
  score: number
  retrieval_score: number
  visual_score: number
  duration: number
  matched_keyword: string
  source: string
  width: number
  height: number
  recommended_clip_duration: number | null
  keyword_scores: Record<string, number> | null
  asset_id: string
  clip_id: string
}

export interface CollectorJobSnapshot {
  job_id: string
  status: string
  target_clips: number
  selected_clips_count: number
  min_acceptable_clips: number
  local_reused: number
  new_downloads: number
  cache_hit_pct: number | null
  [key: string]: unknown
}

export interface WorkspaceMedia {
  video_source: string
  video_aspect: string
  video_concat_mode: string
  video_transition_mode: string | null
  video_clip_duration: number
  video_count: number
  collector_target_clips: number | null
  collector_min_acceptable_clips: number | null
  last_collector_job: CollectorJobSnapshot | null
  video_materials: unknown[] | null
  video_clips: CollectorSelectedClip[] | null
}

export interface WorkspaceVoice {
  voice_name: string
  voice_volume: number
  voice_rate: number
  tts_server: string
  custom_audio_file: string | null
}

export interface WorkspaceBgm {
  bgm_type: string
  bgm_profile: string
  bgm_file: string
  bgm_volume: number
}

export interface WorkspaceSubtitle {
  subtitle_enabled: boolean
  font_name: string
  font_size: number
  subtitle_position: string
  custom_position: number
  text_fore_color: string
  stroke_color: string
  stroke_width: number
  subtitle_background_enabled: boolean
  subtitle_background_color: string
  rounded_subtitle_background: boolean
}

export interface WorkspaceTitleOverlay {
  title_enabled: boolean
  title_text: string
  title_duration: number
}

export interface WorkspacePreviewState {
  ready: boolean
  last_preview_at: string | null
  last_preview_task_id: string | null
  last_preview_audio_file: string | null
}

export interface WorkspaceRenderState {
  last_render_task_id: string | null
  skip_preview: boolean
}

export interface WorkspacePublishState {
  mode: 'manual' | 'auto' | 'skip'
  platforms: string[]
  auto_upload: boolean
  youtube_privacy_status: string
  last_results: Record<string, unknown>[] | null
  done: boolean
}

export interface Workspace {
  channel_slug: string | null
  active_step: number
  updated_at: string | null
  script: WorkspaceScript
  keywords: WorkspaceKeywords
  media: WorkspaceMedia
  voice: WorkspaceVoice
  bgm: WorkspaceBgm
  subtitle: WorkspaceSubtitle
  title_overlay: WorkspaceTitleOverlay
  overrides: string[]
  preview: WorkspacePreviewState
  render: WorkspaceRenderState
  publish: WorkspacePublishState
}

// Deep-partial patch body for PATCH /cockpit/workspace -- matches
// WorkspacePatch's loosely-typed dict fields server-side.
export type WorkspacePatchBody = {
  active_step?: number
  script?: Partial<WorkspaceScript>
  keywords?: Partial<WorkspaceKeywords>
  media?: Partial<WorkspaceMedia>
  voice?: Partial<WorkspaceVoice>
  bgm?: Partial<WorkspaceBgm>
  subtitle?: Partial<WorkspaceSubtitle>
  title_overlay?: Partial<WorkspaceTitleOverlay>
  preview?: Partial<WorkspacePreviewState>
  render?: Partial<WorkspaceRenderState>
  publish?: Partial<WorkspacePublishState>
}

export const STEP_IDS = [
  'script',
  'collector',
  'preview',
  'render',
  'result',
  'publish',
] as const

export type StepId = (typeof STEP_IDS)[number]
export type StepState = 'done' | 'active' | 'pending'
