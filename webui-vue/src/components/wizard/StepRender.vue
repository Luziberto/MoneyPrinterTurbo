<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useWorkspaceStore } from '../../stores/workspace'
import { videosApi } from '../../api/videos'
import { ApiError } from '../../api/client'

const workspaceStore = useWorkspaceStore()
const router = useRouter()
const submitting = ref(false)
const errorMessage = ref<string | null>(null)

async function submitRender(force = false) {
  errorMessage.value = null
  submitting.value = true
  try {
    await videosApi.render(workspaceStore.channelSlug, force)
    await workspaceStore.load(workspaceStore.channelSlug)
    router.push('/criar/result')
  } catch (err) {
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div v-if="workspaceStore.workspace" class="step-render">
    <h2>Render</h2>

    <p class="hint">
      Assunto: <strong>{{ workspaceStore.workspace.script.video_subject || '—' }}</strong> ·
      {{ workspaceStore.workspace.keywords.terms.length }} palavra(s)-chave ·
      fonte: {{ workspaceStore.workspace.media.video_source }}
    </p>

    <div class="actions">
      <button :disabled="submitting" @click="submitRender(false)">
        {{ submitting ? 'Enviando…' : 'Renderizar vídeo' }}
      </button>
      <button v-if="errorMessage" class="secondary" :disabled="submitting" @click="submitRender(true)">
        Renderizar mesmo assim
      </button>
    </div>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </div>
</template>

<style scoped>
.step-render {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 32rem;
}

.hint {
  color: var(--cockpit-text-muted);
  font-size: 0.85rem;
}

.actions {
  display: flex;
  gap: 0.6rem;
}

button {
  padding: 0.55rem 1rem;
  border-radius: 0.4rem;
  border: none;
  background: var(--cockpit-accent);
  color: var(--cockpit-accent-contrast);
  font-weight: 600;
}

button.secondary {
  background: var(--cockpit-surface-hover);
  color: var(--cockpit-text);
}

button:disabled {
  opacity: 0.6;
  cursor: default;
}

.error {
  color: var(--cockpit-danger);
  font-size: 0.85rem;
}
</style>
