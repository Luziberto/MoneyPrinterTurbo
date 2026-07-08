import { api } from './client'

// Mirrors app/models/const.py's TASK_STATE_* values.
export const TASK_STATE_FAILED = -1
export const TASK_STATE_COMPLETE = 1
export const TASK_STATE_PROCESSING = 4

export interface TaskState {
  task_id: string
  state: number
  progress: number
  videos?: string[]
  combined_videos?: string[]
  error?: string
  [key: string]: unknown
}

export const videosApi = {
  render: (channelSlug: string | null, force = false) =>
    api.post<{ task_id: string; request_id: string; params: Record<string, unknown> }>(
      '/api/v1/cockpit/render',
      { force },
      { channel_slug: channelSlug ?? undefined },
    ),

  getTask: (taskId: string) => api.get<TaskState>(`/api/v1/tasks/${taskId}`),

  listTasks: (page = 1, pageSize = 20) =>
    api.get<{ tasks: TaskState[]; total: number; page: number; page_size: number }>('/api/v1/tasks', {
      page,
      page_size: pageSize,
    }),

  deleteTask: (taskId: string) => api.delete<void>(`/api/v1/tasks/${taskId}`),
}
