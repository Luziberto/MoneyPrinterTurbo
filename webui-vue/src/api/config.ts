import { api } from './client'

export interface ConfigSnapshot {
  app: Record<string, unknown>
  ui: Record<string, unknown>
  azure: Record<string, unknown>
  siliconflow: Record<string, unknown>
  elevenlabs: Record<string, unknown>
  chatterbox: Record<string, unknown>
}

export type ConfigPatch = Partial<ConfigSnapshot>

export const configApi = {
  get: () => api.get<ConfigSnapshot>('/api/v1/config'),
  put: (patch: ConfigPatch) => api.put<ConfigSnapshot>('/api/v1/config', patch),
}
