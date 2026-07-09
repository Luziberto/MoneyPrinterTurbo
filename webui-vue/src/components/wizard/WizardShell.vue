<script setup lang="ts">
import { computed, ref } from 'vue'
import { ensureAutoScriptReady, scriptStepBusy, scriptStepError } from '../../composables/useScriptStep'
import { useWorkspaceStore } from '../../stores/workspace'
import { STEP_IDS } from '../../types/workspace'

const props = defineProps<{ activeStep: string }>()
const emit = defineEmits<{ navigate: [stepId: string] }>()

const workspaceStore = useWorkspaceStore()
const leavingScript = ref(false)

const stepLabels: Record<string, string> = {
  script: 'Roteiro',
  collector: 'Coletor',
  preview: 'Preview',
  render: 'Render',
  result: 'Resultado',
}

const steps = computed(() =>
  STEP_IDS.map((id, index) => ({
    id,
    label: stepLabels[id],
    state: workspaceStore.steps?.states[index] ?? 'pending',
  })),
)

async function goTo(stepId: string) {
  if (props.activeStep === 'script' && stepId !== 'script') {
    leavingScript.value = true
    scriptStepError.value = null
    const ok = await ensureAutoScriptReady()
    leavingScript.value = false
    if (!ok) return
  }
  emit('navigate', stepId)
}

function stepClass(step: { id: string; state: string }) {
  const isCurrent = step.id === props.activeStep
  const base =
    'flex items-center gap-2.5 rounded-lg border-l-[3px] border-transparent px-3.5 py-2.5 text-left text-sm transition hover:bg-indigo-500/10 hover:text-slate-100'
  if (isCurrent) {
    return `${base} border-l-indigo-400 bg-indigo-500/20 font-semibold text-slate-50 light:text-slate-900`
  }
  return `${base} text-slate-500`
}

function dotClass(state: string, isCurrent: boolean) {
  if (isCurrent) return 'bg-indigo-200'
  if (state === 'done') return 'bg-emerald-400'
  if (state === 'active') return 'bg-indigo-400'
  return 'bg-slate-600'
}
</script>

<template>
  <div class="grid grid-cols-1 items-start gap-5 xl:grid-cols-[12.5rem_minmax(0,1fr)]">
    <nav class="flex flex-col gap-0.5" aria-label="Pipeline steps">
      <button
        v-for="step in steps"
        :key="step.id"
        type="button"
        :class="stepClass(step)"
        :disabled="leavingScript || scriptStepBusy"
        @click="goTo(step.id)"
      >
        <span
          class="size-1.5 shrink-0 rounded-full"
          :class="dotClass(step.state, step.id === props.activeStep)"
        />
        {{ step.label }}
      </button>
    </nav>
    <div
      class="min-h-[26rem] min-w-0 rounded-xl border border-slate-600/20 bg-slate-900/45 p-3 sm:px-6 sm:py-4 light:border-slate-200 light:bg-white light:shadow-sm light:shadow-slate-200/50"
    >
      <slot />
    </div>
  </div>
</template>
