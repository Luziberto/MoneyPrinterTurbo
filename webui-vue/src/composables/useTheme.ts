import { computed, ref } from 'vue'

const STORAGE_KEY = 'mpt-cockpit-theme'
export type ThemeMode = 'light' | 'dark'

function readStoredTheme(): ThemeMode {
  return localStorage.getItem(STORAGE_KEY) === 'light' ? 'light' : 'dark'
}

const theme = ref<ThemeMode>(readStoredTheme())

export function applyTheme(mode: ThemeMode) {
  theme.value = mode
  document.documentElement.dataset.theme = mode
  localStorage.setItem(STORAGE_KEY, mode)
}

export function initTheme() {
  applyTheme(readStoredTheme())
}

export function useTheme() {
  const isDark = computed(() => theme.value === 'dark')

  function toggleTheme() {
    applyTheme(theme.value === 'dark' ? 'light' : 'dark')
  }

  function setTheme(mode: ThemeMode) {
    applyTheme(mode)
  }

  return { theme, isDark, toggleTheme, setTheme }
}
