import { ref } from 'vue'
import { llmApi } from '../api/llm'
import { ApiError } from '../api/client'
import { paragraphNumberFromTargetDuration } from '../lib/target-duration'
import { useDashboardStore } from '../stores/dashboard'
import { useWorkspaceStore } from '../stores/workspace'
import type { CollectorKeyword, Workspace } from '../types/workspace'

export const scriptStepError = ref<string | null>(null)
export const scriptStepBusy = ref(false)

export function isManualScriptMode(mode: string): boolean {
  return mode === 'verbatim' || mode === 'polish'
}

export function createKeyword(term: string): CollectorKeyword {
  const normalized = term.trim()
  return {
    term: normalized,
    weight: 1,
    visual_intent: '',
    alternatives: [],
    required_concepts: [],
    optional_concepts: [],
  }
}

function channelTargetDuration(): string {
  const dashboardStore = useDashboardStore()
  return String(dashboardStore.channelRuntime?.target_duration ?? '')
}

function scriptTiming(ws: Workspace) {
  const targetDuration = channelTargetDuration()
  const paragraphNumber = targetDuration
    ? paragraphNumberFromTargetDuration(targetDuration)
    : ws.script.paragraph_number
  return { targetDuration, paragraphNumber }
}

function scriptPayload(ws: Workspace) {
  const { targetDuration, paragraphNumber } = scriptTiming(ws)
  return {
    video_subject: ws.script.video_subject,
    video_language: ws.script.video_language,
    paragraph_number: paragraphNumber,
    target_duration: targetDuration,
    video_script_prompt: ws.script.video_script_prompt,
    custom_system_prompt: ws.script.use_custom_system_prompt ? ws.script.custom_system_prompt : '',
  }
}

export async function ensureAutoScriptReady(): Promise<boolean> {
  const workspaceStore = useWorkspaceStore()
  const ws = workspaceStore.workspace
  if (!ws || isManualScriptMode(ws.script.script_mode)) return true

  const subject = ws.script.video_subject.trim()
  if (!subject) {
    scriptStepError.value = 'Informe o assunto do vídeo.'
    return false
  }

  const hasScript = Boolean(ws.script.video_script.trim())
  const hasTerms = ws.keywords.terms.length > 0
  if (hasScript && hasTerms) return true

  scriptStepBusy.value = true
  scriptStepError.value = null
  try {
    let script = ws.script.video_script.trim()
    if (!script) {
      const result = await llmApi.generateScript(scriptPayload(ws))
      if (result.video_script.startsWith('Error:')) {
        scriptStepError.value = result.video_script
        return false
      }
      script = result.video_script
      await workspaceStore.patch({ script: { video_script: script } })
    }

    const current = workspaceStore.workspace
    if (current && current.keywords.terms.length === 0) {
      const { targetDuration, paragraphNumber } = scriptTiming(current)
      const termsResult = await llmApi.generateTerms({
        video_subject: current.script.video_subject,
        video_script: current.script.video_script,
        match_materials_to_script: current.script.match_materials_to_script,
        paragraph_number: paragraphNumber,
        target_duration: targetDuration,
      })
      if (typeof termsResult.video_terms === 'string') {
        scriptStepError.value = termsResult.video_terms
        return false
      }
      await workspaceStore.patch({
        keywords: {
          terms: termsResult.video_terms,
          has_explicit_weights: termsResult.has_explicit_weights ?? false,
        },
      })
    }
    return true
  } catch (err) {
    scriptStepError.value = err instanceof ApiError ? err.message : String(err)
    return false
  } finally {
    scriptStepBusy.value = false
  }
}

export async function polishCurrentScript(): Promise<boolean> {
  const workspaceStore = useWorkspaceStore()
  const ws = workspaceStore.workspace
  if (!ws) return false

  const brief = ws.script.video_script.trim()
  if (!brief) {
    scriptStepError.value = 'Escreva um rascunho no campo de roteiro para polir.'
    return false
  }

  scriptStepBusy.value = true
  scriptStepError.value = null
  try {
    const { targetDuration, paragraphNumber } = scriptTiming(ws)
    const result = await llmApi.polishScript({
      brief,
      video_subject: ws.script.video_subject,
      video_language: ws.script.video_language,
      paragraph_number: paragraphNumber,
      target_duration: targetDuration,
    })
    if (result.video_script.startsWith('Error:')) {
      scriptStepError.value = result.video_script
      return false
    }
    await workspaceStore.patch({
      script: { video_script: result.video_script, script_mode: 'verbatim' },
    })
    return true
  } catch (err) {
    scriptStepError.value = err instanceof ApiError ? err.message : String(err)
    return false
  } finally {
    scriptStepBusy.value = false
  }
}
