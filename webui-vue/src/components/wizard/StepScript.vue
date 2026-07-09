<script setup lang="ts">
import { computed, ref } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'
import { btnPrimaryClass, inputClass, labelClass, selectClass } from '../../lib/cockpit-ui'
import {
  formatTargetDurationLabel,
  paragraphNumberFromTargetDuration,
} from '../../lib/target-duration'
import { useDashboardStore } from '../../stores/dashboard'
import {
  createKeyword,
  isManualScriptMode,
  polishCurrentScript,
  scriptStepBusy,
  scriptStepError,
} from '../../composables/useScriptStep'
import { useUiStore } from '../../stores/ui'
import TopicsQueuePanel from './TopicsQueuePanel.vue'
import { X } from '../../lib/cockpit-icons'
import type { CollectorKeyword } from '../../types/workspace'

const uiStore = useUiStore()
const workspaceStore = useWorkspaceStore()
const dashboardStore = useDashboardStore()
const newKeyword = ref('')

const isManual = computed(() => {
  const mode = workspaceStore.workspace?.script.script_mode ?? 'auto'
  return isManualScriptMode(mode)
})

const scriptReadonly = computed(() => !isManual.value && Boolean(workspaceStore.workspace?.script.video_script.trim()))

const scriptDurationLabel = computed(() =>
  formatTargetDurationLabel(String(dashboardStore.channelRuntime?.target_duration ?? '')),
)

const derivedParagraphs = computed(() =>
  paragraphNumberFromTargetDuration(String(dashboardStore.channelRuntime?.target_duration ?? '')),
)

const scriptPlaceholder = computed(() =>
  isManual.value
    ? 'Escreva ou cole o roteiro completo'
    : 'Gerado automaticamente ao avançar para o próximo passo',
)

function ws() {
  if (!workspaceStore.workspace) throw new Error('workspace not loaded')
  return workspaceStore.workspace
}

async function onSubjectChange(event: Event) {
  await workspaceStore.patch({ script: { video_subject: (event.target as HTMLInputElement).value } })
}

async function onScriptChange(event: Event) {
  await workspaceStore.patch({ script: { video_script: (event.target as HTMLTextAreaElement).value } })
}

async function onModeChange(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  await workspaceStore.patch({
    script: { script_mode: value === 'manual' ? 'verbatim' : 'auto' },
  })
}

async function polishScript() {
  await polishCurrentScript()
}

async function addKeyword() {
  const term = newKeyword.value.trim()
  if (!term) return
  const terms = [...ws().keywords.terms]
  if (terms.some((item) => item.term.toLowerCase() === term.toLowerCase())) {
    newKeyword.value = ''
    return
  }
  terms.push(createKeyword(term))
  newKeyword.value = ''
  await workspaceStore.patch({
    keywords: { terms, has_explicit_weights: ws().keywords.has_explicit_weights },
  })
}

async function removeKeyword(index: number) {
  const terms = ws().keywords.terms.filter((_, i) => i !== index)
  await workspaceStore.patch({
    keywords: { terms, has_explicit_weights: ws().keywords.has_explicit_weights },
  })
}

function keywordLabel(term: CollectorKeyword) {
  if (!ws().keywords.has_explicit_weights) return term.term
  return `${term.term} (${term.weight.toFixed(2)})`
}
</script>

<template>
  <div
    v-if="workspaceStore.workspace"
    class="grid grid-cols-1 items-start gap-5 xl:grid-cols-[minmax(0,1fr)_38rem]"
  >
    <div class="flex min-w-0 flex-col gap-4">
      <h2 class="text-[1.65rem] font-bold tracking-tight">Roteiro</h2>

      <label class="flex flex-col gap-1.5">
        <span :class="labelClass">Assunto</span>
        <input
          type="text"
          :class="inputClass"
          :value="workspaceStore.workspace.script.video_subject"
          placeholder="Sobre o que é o vídeo?"
          @change="onSubjectChange"
        />
      </label>

      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div class="flex flex-col gap-1.5" :class="{ 'sm:col-span-2': isManual }">
          <span :class="labelClass">{{ uiStore.tr('Script Mode') }}</span>
          <div class="flex items-center gap-2">
            <select
              :class="[selectClass, 'min-w-0 flex-1']"
              :value="isManual ? 'manual' : 'auto'"
              @change="onModeChange"
            >
              <option value="auto">{{ uiStore.tr('Script Mode Auto') }}</option>
              <option value="manual">{{ uiStore.tr('Cockpit Script Mode Manual') }}</option>
            </select>
            <button
              v-if="isManual"
              type="button"
              :class="[btnPrimaryClass, 'shrink-0 whitespace-nowrap px-3 py-2 text-sm']"
              :disabled="scriptStepBusy || !workspaceStore.workspace.script.video_script.trim()"
              @click="polishScript"
            >
              {{ scriptStepBusy ? uiStore.tr('Cockpit Loading') : uiStore.tr('Cockpit Script Polish') }}
            </button>
          </div>
        </div>
        <div v-if="!isManual" class="flex flex-col gap-1.5">
          <span :class="labelClass">{{ uiStore.tr('Cockpit Target Duration') }}</span>
          <div :class="[inputClass, 'opacity-90']">
            {{ scriptDurationLabel }}
            <span class="cockpit-muted text-xs"> · {{ derivedParagraphs }} parágrafos</span>
          </div>
        </div>
      </div>

      <label class="flex flex-col gap-1.5">
        <span :class="labelClass">Roteiro</span>
        <textarea
          rows="8"
          :class="[inputClass, 'resize-y', scriptReadonly ? 'opacity-90' : '']"
          :value="workspaceStore.workspace.script.video_script"
          :placeholder="scriptPlaceholder"
          :readonly="scriptReadonly"
          @change="onScriptChange"
        />
      </label>

      <p v-if="!isManual" class="cockpit-muted text-xs">
        {{ uiStore.tr('Cockpit Script Auto Hint') }}
      </p>

      <p v-if="scriptStepError" class="text-sm text-rose-400">{{ scriptStepError }}</p>
      <p v-if="scriptStepBusy && !isManual" class="cockpit-muted text-sm">
        {{ uiStore.tr('Cockpit Loading') }}…
      </p>

      <div v-if="isManual" class="flex flex-col gap-2">
        <span :class="labelClass">{{ uiStore.tr('Cockpit Keywords Title') }}</span>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="(term, index) in workspaceStore.workspace.keywords.terms"
            :key="`${term.term}-${index}`"
            class="inline-flex items-center gap-1 rounded-full bg-slate-800/80 py-1 pr-1 pl-2.5 text-xs light:bg-slate-100"
          >
            {{ keywordLabel(term) }}
            <button
              type="button"
              class="grid size-5 place-items-center rounded-full text-slate-400 transition hover:bg-slate-700/60 hover:text-rose-300 light:hover:bg-slate-200 light:hover:text-rose-600"
              :title="uiStore.tr('Cockpit Keywords Remove')"
              @click="removeKeyword(index)"
            >
              <X :size="12" />
            </button>
          </span>
        </div>
        <div class="flex gap-2">
          <input
            v-model="newKeyword"
            type="text"
            :class="[inputClass, 'min-w-0 flex-1']"
            :placeholder="uiStore.tr('Cockpit Keywords Placeholder')"
            @keyup.enter="addKeyword"
          />
          <button
            type="button"
            :class="[btnPrimaryClass, 'shrink-0 px-3']"
            :disabled="!newKeyword.trim()"
            @click="addKeyword"
          >
            {{ uiStore.tr('Cockpit Keywords Add') }}
          </button>
        </div>
      </div>

      <div
        v-else-if="workspaceStore.workspace.keywords.terms.length > 0"
        class="flex flex-col gap-2"
      >
        <span :class="labelClass">{{ uiStore.tr('Cockpit Keywords Title') }}</span>
        <ul class="flex flex-wrap gap-1.5 p-0 list-none">
          <li
            v-for="term in workspaceStore.workspace.keywords.terms"
            :key="term.term"
            class="rounded-full bg-slate-800/80 px-2.5 py-1 text-xs light:bg-slate-100"
          >
            {{ keywordLabel(term) }}
          </li>
        </ul>
      </div>
    </div>

    <TopicsQueuePanel class="hidden w-full self-start xl:flex" />
  </div>
</template>
