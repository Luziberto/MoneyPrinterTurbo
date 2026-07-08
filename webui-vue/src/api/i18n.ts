import { api } from './client'

export interface LocaleFile {
  Language: string
  Translation: Record<string, string>
}

export const KNOWN_LOCALES = ['de', 'en', 'es', 'id', 'pt', 'ru', 'tr', 'vi', 'zh'] as const
export type LocaleCode = (typeof KNOWN_LOCALES)[number]

export const i18nApi = {
  getLocale: (locale: LocaleCode) => api.get<LocaleFile>(`/api/v1/i18n/${locale}`),
}
