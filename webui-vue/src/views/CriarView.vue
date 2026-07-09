<script setup lang="ts">
import { computed, ref } from 'vue'
import WizardShell from '../components/wizard/WizardShell.vue'
import StepScript from '../components/wizard/StepScript.vue'
import StepCollector from '../components/wizard/StepCollector.vue'
import StepPreview from '../components/wizard/StepPreview.vue'
import StepRender from '../components/wizard/StepRender.vue'
import StepResult from '../components/wizard/StepResult.vue'
import { provideWizardNavigation } from '../composables/useWizardNavigation'
import type { StepId } from '../types/workspace'

const activeStep = ref<StepId>('script')
provideWizardNavigation((stepId) => {
  activeStep.value = stepId
})

const stepComponents: Record<string, unknown> = {
  script: StepScript,
  collector: StepCollector,
  preview: StepPreview,
  render: StepRender,
  result: StepResult,
}

const activeComponent = computed(() => stepComponents[activeStep.value] ?? StepScript)

function onNavigate(stepId: string) {
  activeStep.value = stepId as StepId
}
</script>

<template>
  <WizardShell :active-step="activeStep" @navigate="onNavigate">
    <component :is="activeComponent" />
  </WizardShell>
</template>
