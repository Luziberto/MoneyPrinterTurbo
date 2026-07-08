<script setup lang="ts">
import { computed } from 'vue'
import WizardShell from '../components/wizard/WizardShell.vue'
import StepScript from '../components/wizard/StepScript.vue'
import StepCollector from '../components/wizard/StepCollector.vue'
import StepPreview from '../components/wizard/StepPreview.vue'
import StepRender from '../components/wizard/StepRender.vue'
import StepResult from '../components/wizard/StepResult.vue'
import StepPublish from '../components/wizard/StepPublish.vue'

const props = defineProps<{ step: string }>()

const stepComponents: Record<string, unknown> = {
  script: StepScript,
  collector: StepCollector,
  preview: StepPreview,
  render: StepRender,
  result: StepResult,
  publish: StepPublish,
}

const activeComponent = computed(() => stepComponents[props.step] ?? StepScript)
</script>

<template>
  <WizardShell :active-step="step">
    <component :is="activeComponent" />
  </WizardShell>
</template>
