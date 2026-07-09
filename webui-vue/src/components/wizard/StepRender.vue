<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useWorkspaceStore } from '../../stores/workspace'
import { videosApi } from '../../api/videos'
import { ApiError } from '../../api/client'
import { btnPrimaryClass } from '../../lib/cockpit-ui'

const workspaceStore = useWorkspaceStore()
const router = useRouter()
const submitting = ref(false)
const errorMessage = ref<string | null>(null)

const btnSecondaryClass =
  'inline-flex items-center justify-center rounded-lg border border-slate-600/30 bg-slate-800/80 px-4 py-2.5 text-sm font-semibold text-slate-100 transition hover:bg-slate-700 disabled:cursor-default disabled:opacity-55'

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
  <div v-if="workspaceStore.workspace" class="flex max-w-lg flex-col gap-4">
    <h2 class="text-xl font-bold tracking-tight">Render</h2>

    <p class="text-sm text-slate-500">
      Assunto: <strong class="text-slate-200">{{ workspaceStore.workspace.script.video_subject || '—' }}</strong>
      · {{ workspaceStore.workspace.keywords.terms.length }} palavra(s)-chave · fonte:
      {{ workspaceStore.workspace.media.video_source }}
    </p>

    <div class="flex flex-wrap gap-2.5">
      <button :class="btnPrimaryClass" :disabled="submitting" @click="submitRender(false)">
        {{ submitting ? 'Enviando…' : 'Renderizar vídeo' }}
      </button>
      <button
        v-if="errorMessage"
        :class="btnSecondaryClass"
        :disabled="submitting"
        @click="submitRender(true)"
      >
        Renderizar mesmo assim
      </button>
    </div>

    <p v-if="errorMessage" class="text-sm text-rose-400">{{ errorMessage }}</p>
  </div>
</template>
