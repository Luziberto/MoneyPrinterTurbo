<script setup lang="ts">
import { ref } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'
import { llmApi } from '../../api/llm'
import { ApiError } from '../../api/client'

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
  <div v-if="workspaceStore.workspace" class="step-script">
    <h2>Roteiro</h2>

    <label class="field">
      <span>Assunto</span>
      <input
        type="text"
        :value="workspaceStore.workspace.script.video_subject"
        @change="onSubjectChange"
        placeholder="Sobre o que é o vídeo?"
      />
    </label>

    <div class="field-row">
      <label class="field">
        <span>Parágrafos</span>
        <input
          type="number"
          min="1"
          max="10"
          :value="workspaceStore.workspace.script.paragraph_number"
          @change="onParagraphChange"
        />
      </label>
      <label class="field">
        <span>Modo</span>
        <select :value="workspaceStore.workspace.script.script_mode" @change="onScriptModeChange">
          <option value="auto">Automático</option>
          <option value="verbatim">Verbatim</option>
          <option value="polish">Polir</option>
        </select>
      </label>
    </div>

    <label class="field">
      <span>Roteiro</span>
      <textarea
        rows="8"
        :value="workspaceStore.workspace.script.video_script"
        @change="onScriptChange"
        placeholder="Deixe em branco para gerar automaticamente"
      />
    </label>

    <div class="actions">
      <button :disabled="generatingScript" @click="generateScript">
        {{ generatingScript ? 'Gerando…' : 'Gerar roteiro' }}
      </button>
      <button :disabled="generatingTerms" @click="generateTerms">
        {{ generatingTerms ? 'Gerando…' : 'Gerar palavras-chave' }}
      </button>
    </div>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>

    <div v-if="workspaceStore.workspace.keywords.terms.length > 0" class="keywords">
      <h3>Palavras-chave</h3>
      <ul>
        <li v-for="term in workspaceStore.workspace.keywords.terms" :key="term.term">
          {{ term.term }} <span class="keywords__weight">({{ term.weight.toFixed(2) }})</span>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.step-script {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 40rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.85rem;
  color: var(--cockpit-text-muted);
}

.field input,
.field select,
.field textarea {
  padding: 0.5rem 0.6rem;
  border-radius: 0.4rem;
  border: 1px solid var(--cockpit-border);
  background: var(--cockpit-bg);
  color: var(--cockpit-text);
  font-family: inherit;
  resize: vertical;
}

.field-row {
  display: flex;
  gap: 1rem;
}

.actions {
  display: flex;
  gap: 0.6rem;
}

.actions button {
  padding: 0.55rem 1rem;
  border-radius: 0.4rem;
  border: none;
  background: var(--cockpit-accent);
  color: var(--cockpit-accent-contrast);
  font-weight: 600;
}

.actions button:disabled {
  opacity: 0.6;
  cursor: default;
}

.error {
  color: var(--cockpit-danger);
  font-size: 0.85rem;
}

.keywords ul {
  list-style: none;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.keywords li {
  padding: 0.25rem 0.6rem;
  border-radius: 999px;
  background: var(--cockpit-surface-hover);
  font-size: 0.8rem;
}

.keywords__weight {
  color: var(--cockpit-text-muted);
}
</style>
