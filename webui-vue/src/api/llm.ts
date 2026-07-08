import { api } from './client'
import type { CollectorKeyword } from '../types/workspace'

export const llmApi = {
  generateScript: (body: {
    video_subject: string
    video_language: string
    paragraph_number: number
    video_script_prompt: string
    custom_system_prompt: string
  }) => api.post<{ video_script: string }>('/api/v1/scripts', body),

  generateTerms: (body: {
    video_subject: string
    video_script: string
    amount: number
    match_materials_to_script: boolean
  }) =>
    api.post<{ video_terms: CollectorKeyword[] | string; has_explicit_weights?: boolean }>(
      '/api/v1/terms',
      body,
    ),
}
