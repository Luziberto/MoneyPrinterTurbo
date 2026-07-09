<script setup lang="ts">
import { ref } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'
import { ApiError } from '../../api/client'
import { btnPrimaryClass } from '../../lib/cockpit-ui'

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
  <div v-if="workspaceStore.workspace" class="flex max-w-lg flex-col gap-4">
    <h2 class="text-xl font-bold tracking-tight">Preview</h2>

    <ul class="flex list-none flex-col gap-1.5 p-0 text-sm text-slate-500">
      <li :class="{ 'text-emerald-400': workspaceStore.workspace.script.video_script }">
        Roteiro {{ workspaceStore.workspace.script.video_script ? 'pronto' : 'pendente' }}
      </li>
      <li :class="{ 'text-emerald-400': workspaceStore.workspace.keywords.terms.length > 0 }">
        {{ workspaceStore.workspace.keywords.terms.length }} palavra(s)-chave
      </li>
    </ul>

    <label class="flex items-center gap-2 text-sm">
      <input v-model="includeAudio" type="checkbox" class="accent-indigo-500" />
      <span>Gerar amostra de áudio (TTS)</span>
    </label>

    <button :class="btnPrimaryClass" :disabled="workspaceStore.loading" @click="runPreview">
      {{ workspaceStore.loading ? 'Rodando…' : 'Rodar preview' }}
    </button>

    <p v-if="errorMessage" class="text-sm text-rose-400">{{ errorMessage }}</p>

    <p v-if="workspaceStore.workspace.preview.ready" class="text-sm text-emerald-400">
      Preview pronto em {{ workspaceStore.workspace.preview.last_preview_at }}
    </p>

    <audio v-if="workspaceStore.previewAudioUrl" :src="workspaceStore.previewAudioUrl" controls class="w-full" />
  </div>
</template>
