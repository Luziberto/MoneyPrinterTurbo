/** BCP-47 codes supported for script/TTS generation (mirrors webui/Main.py support_locales). */
export const VIDEO_LANGUAGE_CODES = [
  'pt-BR',
  'zh-CN',
  'zh-HK',
  'zh-TW',
  'de-DE',
  'en-US',
  'es-ES',
  'fr-FR',
  'id-ID',
  'ja-JP',
  'ko-KR',
  'ru-RU',
  'vi-VN',
  'th-TH',
  'tr-TR',
] as const

export type VideoLanguageCode = (typeof VIDEO_LANGUAGE_CODES)[number]

export function videoLanguageOptions(current?: string | null): Array<{ value: string; label: string }> {
  const options: Array<{ value: string; label: string }> = [{ value: '', label: 'Auto Detect' }]
  const seen = new Set<string>()

  for (const code of VIDEO_LANGUAGE_CODES) {
    options.push({ value: code, label: code })
    seen.add(code)
  }

  const normalized = String(current ?? '').trim()
  if (normalized && !seen.has(normalized)) {
    options.push({ value: normalized, label: normalized })
  }

  return options
}
