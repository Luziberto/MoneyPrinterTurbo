<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useWorkspaceStore } from '../../stores/workspace'
import { STEP_IDS } from '../../types/workspace'

const props = defineProps<{ activeStep: string }>()

const router = useRouter()
const workspaceStore = useWorkspaceStore()

const stepLabels: Record<string, string> = {
  script: 'Roteiro',
  collector: 'Coletor',
  preview: 'Preview',
  render: 'Render',
  result: 'Resultado',
  publish: 'Publicar',
}

const steps = computed(() =>
  STEP_IDS.map((id, index) => ({
    id,
    label: stepLabels[id],
    state: workspaceStore.steps?.states[index] ?? 'pending',
  })),
)

function goTo(stepId: string) {
  router.push(`/criar/${stepId}`)
}

defineExpose({ props })
</script>

<template>
  <div class="wizard">
    <nav class="wizard__nav">
      <button
        v-for="step in steps"
        :key="step.id"
        class="wizard__step"
        :class="[`wizard__step--${step.state}`, { 'wizard__step--current': step.id === props.activeStep }]"
        @click="goTo(step.id)"
      >
        <span class="wizard__dot" />
        {{ step.label }}
      </button>
    </nav>
    <div class="wizard__body">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.wizard {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 1.5rem;
  align-items: start;
}

.wizard__nav {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  position: sticky;
  top: 1.5rem;
}

.wizard__step {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.55rem 0.75rem;
  border: none;
  border-radius: 0.5rem;
  background: transparent;
  color: var(--cockpit-text-muted);
  font-size: 0.88rem;
  text-align: left;
}

.wizard__step:hover {
  background: var(--cockpit-surface-hover);
}

.wizard__step--current {
  background: var(--cockpit-surface);
  color: var(--cockpit-text);
  font-weight: 600;
  box-shadow: 0 0 0 1px var(--cockpit-border);
}

.wizard__dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--cockpit-border);
  flex-shrink: 0;
}

.wizard__step--done .wizard__dot {
  background: var(--cockpit-success);
}

.wizard__step--active .wizard__dot {
  background: var(--cockpit-accent);
}

.wizard__body {
  background: var(--cockpit-surface);
  border: 1px solid var(--cockpit-border);
  border-radius: 0.75rem;
  padding: 1.5rem;
  min-height: 24rem;
}
</style>
