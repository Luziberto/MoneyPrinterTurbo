<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'
import { useUiStore } from '../../stores/ui'
import { collectorApi } from '../../api/collector'
import { ApiError } from '../../api/client'
import { btnPrimaryClass, cardClass } from '../../lib/cockpit-ui'

const workspaceStore = useWorkspaceStore()
const uiStore = useUiStore()
const fetching = ref(false)
const errorMessage = ref<string | null>(null)
const jobStatus = ref<string | null>(null)
let pollTimer: ReturnType<typeof setTimeout> | null = null

const lastJob = computed(() => workspaceStore.workspace?.media.last_collector_job ?? null)
const usesCollector = computed(
  () => workspaceStore.workspace?.media.video_source === 'collector',
)

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
  <div v-if="workspaceStore.workspace" class="flex max-w-lg flex-col gap-4">
    <h2 class="text-xl font-bold tracking-tight">Coletor de mídia</h2>

    <p class="text-sm text-slate-500">
      {{ uiStore.tr('Cockpit Collector Step Hint') }}
    </p>

    <template v-if="usesCollector">
      <button :class="btnPrimaryClass" :disabled="fetching" @click="fetchClips">
        {{ fetching ? `Buscando… (${jobStatus})` : 'Buscar clipes' }}
      </button>

      <p v-if="errorMessage" class="text-sm text-rose-400">{{ errorMessage }}</p>

      <div v-if="lastJob" :class="[cardClass, 'grid gap-1 text-sm']">
        <div><strong>Status:</strong> {{ lastJob.status }}</div>
        <div><strong>Clipes selecionados:</strong> {{ lastJob.selected_clips_count }}</div>
        <div><strong>Reaproveitados:</strong> {{ lastJob.local_reused }}</div>
        <div><strong>Novos downloads:</strong> {{ lastJob.new_downloads }}</div>
        <div v-if="lastJob.cache_hit_pct !== null">
          <strong>Cache hit:</strong> {{ lastJob.cache_hit_pct }}%
        </div>
      </div>
    </template>
    <p v-else class="text-sm text-slate-500">
      Fonte atual: <strong class="text-slate-300">{{ workspaceStore.workspace.media.video_source }}</strong>.
      {{ uiStore.tr('Cockpit Collector Step NonCollector') }}
    </p>
  </div>
</template>
