import { inject, provide, type InjectionKey } from 'vue'
import type { StepId } from '../types/workspace'

export type NavigateToStep = (stepId: StepId) => void

const WIZARD_NAVIGATE_KEY: InjectionKey<NavigateToStep> = Symbol('wizard-navigate')

export function provideWizardNavigation(navigate: NavigateToStep) {
  provide(WIZARD_NAVIGATE_KEY, navigate)
}

// Steps that need to programmatically advance (e.g. StepRender jumping to
// 'result' after a render is submitted) inject this instead of touching the
// router directly -- the wizard's step is CriarView's local state, not a
// route, since Phase C's routing overhaul (see router/index.ts).
export function useWizardNavigation(): NavigateToStep {
  const navigate = inject(WIZARD_NAVIGATE_KEY)
  if (!navigate) {
    throw new Error('useWizardNavigation() called outside of CriarView\'s wizard tree')
  }
  return navigate
}
