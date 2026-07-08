<script setup lang="ts">
import { ref } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'
import { ApiError } from '../../api/client'

const workspaceStore = useWorkspaceStore()
const includeAudio = ref(false)
const errorMessage = ref<string | null>(null)

async function runPreview() {
  errorMessage.value = null
  try {
    await workspaceStore.runPreview(includeAudio.value)
  } catch (err) {
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
  }
}
</script>

<template>
  <div v-if="workspaceStore.workspace" class="step-preview">
    <h2>Preview</h2>

    <ul class="checklist">
      <li :class="{ ok: workspaceStore.workspace.script.video_script }">
        Roteiro {{ workspaceStore.workspace.script.video_script ? 'pronto' : 'pendente' }}
      </li>
      <li :class="{ ok: workspaceStore.workspace.keywords.terms.length > 0 }">
        {{ workspaceStore.workspace.keywords.terms.length }} palavra(s)-chave
      </li>
    </ul>

    <label class="checkbox">
      <input v-model="includeAudio" type="checkbox" />
      <span>Gerar amostra de áudio (TTS)</span>
    </label>

    <button :disabled="workspaceStore.loading" @click="runPreview">
      {{ workspaceStore.loading ? 'Rodando…' : 'Rodar preview' }}
    </button>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>

    <p v-if="workspaceStore.workspace.preview.ready" class="ready">
      Preview pronto em {{ workspaceStore.workspace.preview.last_preview_at }}
    </p>

    <audio v-if="workspaceStore.previewAudioUrl" :src="workspaceStore.previewAudioUrl" controls />
  </div>
</template>

<style scoped>
.step-preview {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 32rem;
}

.checklist {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  font-size: 0.85rem;
  color: var(--cockpit-text-muted);
}

.checklist .ok {
  color: var(--cockpit-success);
}

.checkbox {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
}

button {
  align-self: flex-start;
  padding: 0.55rem 1rem;
  border-radius: 0.4rem;
  border: none;
  background: var(--cockpit-accent);
  color: var(--cockpit-accent-contrast);
  font-weight: 600;
}

button:disabled {
  opacity: 0.6;
  cursor: default;
}

.error {
  color: var(--cockpit-danger);
  font-size: 0.85rem;
}

.ready {
  color: var(--cockpit-success);
  font-size: 0.85rem;
}

audio {
  width: 100%;
}
</style>
