<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'
import { videosApi, TASK_STATE_COMPLETE, TASK_STATE_FAILED, type TaskState } from '../../api/videos'

const workspaceStore = useWorkspaceStore()
const task = ref<TaskState | null>(null)
const startedAt = ref<number | null>(null)
let pollTimer: ReturnType<typeof setTimeout> | null = null

const taskId = computed(() => workspaceStore.workspace?.render.last_render_task_id ?? null)
const isDone = computed(
  () => task.value?.state === TASK_STATE_COMPLETE || task.value?.state === TASK_STATE_FAILED,
)

function stopPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

async function poll() {
  if (!taskId.value) return
  task.value = await videosApi.getTask(taskId.value)
  if (isDone.value) return

  const elapsed = startedAt.value ? Date.now() - startedAt.value : 0
  const interval = elapsed > 20_000 ? 5000 : 1500
  pollTimer = setTimeout(() => void poll(), interval)
}

function startPolling() {
  stopPolling()
  if (!taskId.value) return
  startedAt.value = Date.now()
  void poll()
}

watch(taskId, startPolling)
onMounted(startPolling)
onUnmounted(stopPolling)
</script>

<template>
  <div class="step-result">
    <h2>Resultado</h2>

    <p v-if="!taskId" class="hint">Nenhum render enviado ainda -- volte ao passo Render.</p>

    <template v-else-if="task">
      <p><strong>Task:</strong> {{ taskId }}</p>
      <p v-if="!isDone">Processando… {{ task.progress }}%</p>
      <p v-if="task.state === TASK_STATE_FAILED" class="error">
        Render falhou{{ task.error ? `: ${task.error}` : '' }}
      </p>

      <div v-if="task.state === TASK_STATE_COMPLETE && task.videos?.length" class="result">
        <video :src="task.videos[0]" controls />
        <a class="download" :href="task.videos[0]" download>Baixar vídeo</a>
        <RouterLink class="publish-link" to="/criar/publish">Ir para Publicar →</RouterLink>
      </div>
    </template>
  </div>
</template>

<style scoped>
.step-result {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 24rem;
}

.hint {
  color: var(--cockpit-text-muted);
  font-size: 0.85rem;
}

.error {
  color: var(--cockpit-danger);
}

.result {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

video {
  width: 100%;
  border-radius: 0.5rem;
  background: black;
}

.download,
.publish-link {
  color: var(--cockpit-accent);
  font-weight: 600;
  text-decoration: none;
}
</style>
