export const SECONDS_PER_PARAGRAPH = 25
export const DURATION_STEP_SECONDS = 10
export const MIN_DURATION_SECONDS = 10
export const MAX_DURATION_SECONDS = 300
export const DEFAULT_TARGET_DURATION = '60-90'

export function durationSecondOptions(
  minSeconds = MIN_DURATION_SECONDS,
  maxSeconds = MAX_DURATION_SECONDS,
  step = DURATION_STEP_SECONDS,
): number[] {
  const options: number[] = []
  for (let value = minSeconds; value <= maxSeconds; value += step) {
    options.push(value)
  }
  return options
}

export function parseTargetDuration(raw: string | null | undefined): { min: number; max: number } {
  const text = String(raw ?? '')
    .trim()
    .toLowerCase()
    .replace(/s/g, '')
  if (!text) {
    return parseTargetDuration(DEFAULT_TARGET_DURATION)
  }

  const numbers = [...text.matchAll(/\d+/g)].map((match) => Number(match[0]))
  if (numbers.length === 0) {
    return parseTargetDuration(DEFAULT_TARGET_DURATION)
  }

  let min = clampDuration(numbers[0]!)
  let max = clampDuration(numbers[1] ?? numbers[0]!)
  if (max < min) [min, max] = [max, min]
  return { min, max }
}

export function formatTargetDuration(minSeconds: number, maxSeconds: number): string {
  let min = clampDuration(minSeconds)
  let max = clampDuration(maxSeconds)
  if (max < min) [min, max] = [max, min]
  if (min === max) return String(min)
  return `${min}-${max}`
}

export function midpointSeconds(minSeconds: number, maxSeconds: number): number {
  const { min, max } = parseTargetDuration(formatTargetDuration(minSeconds, maxSeconds))
  return Math.floor((min + max) / 2)
}

export function paragraphNumberFromTargetDuration(raw: string | null | undefined): number {
  const { min, max } = parseTargetDuration(raw)
  const mid = midpointSeconds(min, max)
  const paragraphs = Math.round(mid / SECONDS_PER_PARAGRAPH)
  return Math.max(1, Math.min(10, paragraphs))
}

export function durationSecondsFromTargetDuration(raw: string | null | undefined): number {
  const { min, max } = parseTargetDuration(raw)
  return Math.max(30, midpointSeconds(min, max))
}

export function formatTargetDurationLabel(raw: string | null | undefined): string {
  const { min, max } = parseTargetDuration(raw)
  if (min === max) return `${min}s`
  return `${min}s–${max}s`
}

function clampDuration(value: number): number {
  const rounded = Math.round(value / DURATION_STEP_SECONDS) * DURATION_STEP_SECONDS
  return Math.max(MIN_DURATION_SECONDS, Math.min(MAX_DURATION_SECONDS, rounded))
}
