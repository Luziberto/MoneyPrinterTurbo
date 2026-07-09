<script setup lang="ts">
import { ref } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'
import { llmApi } from '../../api/llm'
import { ApiError } from '../../api/client'
import { btnPrimaryClass, inputClass, labelClass, selectClass } from '../../lib/cockpit-ui'
import TopicsQueuePanel from './TopicsQueuePanel.vue'

const workspaceStore = useWorkspaceStore()
const generatingScript = ref(false)
const generatingTerms = ref(false)
const errorMessage = ref<string | null>(null)

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

async function onParagraphChange(event: Event) {
  await workspaceStore.patch({
    script: { paragraph_number: Number((event.target as HTMLInputElement).value) },
  })
}

async function onScriptModeChange(event: Event) {
  await workspaceStore.patch({
    script: { script_mode: (event.target as HTMLSelectElement).value as 'auto' | 'verbatim' | 'polish' },
  })
}

async function generateScript() {
  errorMessage.value = null
  generatingScript.value = true
  try {
    const { video_script } = await llmApi.generateScript({
      video_subject: ws().script.video_subject,
      video_language: ws().script.video_language,
      paragraph_number: ws().script.paragraph_number,
      video_script_prompt: ws().script.video_script_prompt,
      custom_system_prompt: ws().script.use_custom_system_prompt ? ws().script.custom_system_prompt : '',
    })
    if (video_script.startsWith('Error:')) {
      errorMessage.value = video_script
      return
    }
    await workspaceStore.patch({ script: { video_script } })
  } catch (err) {
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
  } finally {
    generatingScript.value = false
  }
}

async function generateTerms() {
  errorMessage.value = null
  generatingTerms.value = true
  try {
    const result = await llmApi.generateTerms({
      video_subject: ws().script.video_subject,
      video_script: ws().script.video_script,
      amount: ws().script.match_materials_to_script ? 8 : 5,
      match_materials_to_script: ws().script.match_materials_to_script,
    })
    if (typeof result.video_terms === 'string') {
      errorMessage.value = result.video_terms
      return
    }
    await workspaceStore.patch({
      keywords: { terms: result.video_terms, has_explicit_weights: result.has_explicit_weights ?? false },
    })
  } catch (err) {
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
  } finally {
    generatingTerms.value = false
  }
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
      <label class="flex flex-col gap-1.5">
        <span :class="labelClass">Parágrafos</span>
        <input
          type="number"
          min="1"
          max="10"
          :class="inputClass"
          :value="workspaceStore.workspace.script.paragraph_number"
          @change="onParagraphChange"
        />
      </label>
      <label class="flex flex-col gap-1.5">
        <span :class="labelClass">Modo</span>
        <select
          :class="selectClass"
          :value="workspaceStore.workspace.script.script_mode"
          @change="onScriptModeChange"
        >
          <option value="auto">Automático</option>
          <option value="verbatim">Verbatim</option>
          <option value="polish">Polir</option>
        </select>
      </label>
    </div>

    <label class="flex flex-col gap-1.5">
      <span :class="labelClass">Roteiro</span>
      <textarea
        rows="8"
        :class="[inputClass, 'resize-y']"
        :value="workspaceStore.workspace.script.video_script"
        placeholder="Deixe em branco para gerar automaticamente"
        @change="onScriptChange"
      />
    </label>

    <div class="mt-1 flex flex-wrap gap-2.5">
      <button :class="btnPrimaryClass" :disabled="generatingScript" @click="generateScript">
        {{ generatingScript ? 'Gerando…' : 'Gerar roteiro' }}
      </button>
      <button :class="btnPrimaryClass" :disabled="generatingTerms" @click="generateTerms">
        {{ generatingTerms ? 'Gerando…' : 'Gerar palavras-chave' }}
      </button>
    </div>

    <p v-if="errorMessage" class="text-sm text-rose-400">{{ errorMessage }}</p>

    <div v-if="workspaceStore.workspace.keywords.terms.length > 0">
      <h3 class="mb-2 text-sm font-semibold text-slate-400">Palavras-chave</h3>
      <ul class="flex flex-wrap gap-1.5 p-0 list-none">
        <li
          v-for="term in workspaceStore.workspace.keywords.terms"
          :key="term.term"
          class="rounded-full bg-slate-800/80 px-2.5 py-1 text-xs"
        >
          {{ term.term }}
          <span class="text-slate-500">({{ term.weight.toFixed(2) }})</span>
        </li>
      </ul>
    </div>
    </div>

    <TopicsQueuePanel class="hidden w-full self-start xl:flex" />
  </div>
</template>
