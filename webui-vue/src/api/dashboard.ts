import { api } from './client'

// Mirrors app/controllers/v1/dashboard.py::get_dashboard_summary()'s response shape.
export interface VideoRow {
  id: string
  channel_slug: string
  title: string
  subject: string
  thumbnail_path: string | null
  status: string
  error: string | null
  created_at: string
  updated_at: string
  [key: string]: unknown
}

export interface DashboardSummary {
  status_counts: Record<string, number>
  time_window_counts: { today: number; this_week: number; this_month: number }
  provider_health: Record<string, { status: string; detail: string }>
  recent_videos: VideoRow[]
  recent_errors: VideoRow[]
  stage_timing_avg_seconds: Record<string, number | null>
  disk_usage: { total: number; used: number; free: number }
  estimated_minutes_saved: {
    minutes: number
    videos_counted: number
    minutes_per_video: number
    is_estimate: boolean
  }
  queue: {
    lock: Record<string, unknown> | null
    recent_tasks: Record<string, unknown>[]
    total_tasks: number
  }
}

export const dashboardSummaryApi = {
  get: () => api.get<DashboardSummary>('/api/v1/dashboard/summary'),
}
