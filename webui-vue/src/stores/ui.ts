import { defineStore } from 'pinia'
import { i18nApi, type LocaleCode } from '../api/i18n'

const STORAGE_KEY = 'mpt-cockpit-locale'

interface State {
  locale: LocaleCode
  localeLabel: string
  translations: Record<string, string>
  loading: boolean
}

function initialLocale(): LocaleCode {
  const saved = localStorage.getItem(STORAGE_KEY)
  return (saved as LocaleCode) || 'pt'
}

export const useUiStore = defineStore('ui', {
  state: (): State => ({
    locale: initialLocale(),
    localeLabel: '',
    translations: {},
    loading: false,
  }),

  actions: {
    async setLocale(locale: LocaleCode) {
      this.loading = true
      try {
        const { Language, Translation } = await i18nApi.getLocale(locale)
        this.locale = locale
        this.localeLabel = Language
        this.translations = Translation
        localStorage.setItem(STORAGE_KEY, locale)
      } finally {
        this.loading = false
      }
    },

    // tr() falls back to the key itself when a translation hasn't loaded
    // yet or is missing -- this mirrors webui/cockpit.py's tr() call sites
    // key-for-key (see webui/i18n/*.json), so the Phase 5 parity pass is
    // just filling in usages, not inventing new keys.
    tr(key: string): string {
      return this.translations[key] ?? key
    },
  },
})
