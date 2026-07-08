<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'
import { collectorApi } from '../../api/collector'
import { ApiError } from '../../api/client'

const workspaceStore = useWorkspaceStore()
const fetching = ref(false)
const errorMessage = ref<string | null>(null)
const jobStatus = ref<string | null>(null)
let pollTimer: ReturnType<typeof setTimeout> | null = null

const lastJob = computed(() => workspaceStore.workspace?.media.last_collector_job ?? null)

async function onVideoSourceChange(event: Event) {
  await workspaceStore.patch({ media: { video_source: (event.target as HTMLSelectElement).value } })
}

function stopPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

async function pollJob(jobId: string) {
  try {
    const result = await collectorApi.getJob(jobId, workspaceStore.channelSlug ?? undefined)
    jobStatus.value = result.status
    if (result.status === 'ready' || result.status === 'failed' || result.status === 'quota_exceeded') {
      fetching.value = false
      await workspaceStore.load(workspaceStore.channelSlug)
      return
    }
    pollTimer = setTimeout(() => void pollJob(jobId), 2000)
  } catch (err) {
    fetching.value = false
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
  }
}

async function fetchClips() {
  errorMessage.value = null
  const workspace = workspaceStore.workspace
  if (!workspace || workspace.keywords.terms.length === 0) {
    errorMessage.value = 'Gere palavras-chave no passo Roteiro antes de buscar clipes.'
    return
  }
  fetching.value = true
  jobStatus.value = 'pending'
  try {
    const job = await collectorApi.createJob(
      workspace.keywords.terms,
      workspace.media.collector_target_clips ?? 25,
      workspace.media.collector_min_acceptable_clips ?? 20,
      workspaceStore.channelSlug ?? undefined,
    )
    await pollJob(job.job_id)
  } catch (err) {
    fetching.value = false
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
  }
}

onUnmounted(stopPolling)
</script>

<template>
  <div v-if="workspaceStore.workspace" class="step-collector">
    <h2>Coletor de mídia</h2>

    <label class="field">
      <span>Fonte de vídeo</span>
      <select :value="workspaceStore.workspace.media.video_source" @change="onVideoSourceChange">
        <option value="collector">Collector</option>
        <option value="pexels">Pexels</option>
        <option value="pixabay">Pixabay</option>
        <option value="local">Local</option>
      </select>
    </label>

    <template v-if="workspaceStore.workspace.media.video_source === 'collector'">
      <button :disabled="fetching" @click="fetchClips">
        {{ fetching ? `Buscando… (${jobStatus})` : 'Buscar clipes' }}
      </button>

      <p v-if="errorMessage" class="error">{{ errorMessage }}</p>

      <div v-if="lastJob" class="job-snapshot">
        <div><strong>Status:</strong> {{ lastJob.status }}</div>
        <div><strong>Clipes selecionados:</strong> {{ lastJob.selected_clips_count }}</div>
        <div><strong>Reaproveitados:</strong> {{ lastJob.local_reused }}</div>
        <div><strong>Novos downloads:</strong> {{ lastJob.new_downloads }}</div>
        <div v-if="lastJob.cache_hit_pct !== null"><strong>Cache hit:</strong> {{ lastJob.cache_hit_pct }}%</div>
      </div>
    </template>
    <p v-else class="hint">
      Fonte "{{ workspaceStore.workspace.media.video_source }}" não usa o Collector -- os clipes são
      resolvidos no momento do render.
    </p>
  </div>
</template>

<style scoped>
.step-collector {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 32rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.85rem;
  color: var(--cockpit-text-muted);
}

.field select {
  padding: 0.5rem 0.6rem;
  border-radius: 0.4rem;
  border: 1px solid var(--cockpit-border);
  background: var(--cockpit-bg);
  color: var(--cockpit-text);
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

.hint {
  color: var(--cockpit-text-muted);
  font-size: 0.85rem;
}

.job-snapshot {
  display: grid;
  gap: 0.3rem;
  font-size: 0.85rem;
  padding: 0.75rem 1rem;
  background: var(--cockpit-surface-hover);
  border-radius: 0.5rem;
}
</style>
