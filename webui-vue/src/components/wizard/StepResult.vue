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
  <div class="flex max-w-96 flex-col gap-4">
    <h2 class="text-xl font-bold tracking-tight">Resultado</h2>

    <p v-if="!taskId" class="text-sm text-slate-500">
      Nenhum render enviado ainda — volte ao passo Render.
    </p>

    <template v-else-if="task">
      <p class="text-sm"><strong>Task:</strong> {{ taskId }}</p>
      <p v-if="!isDone" class="text-sm text-slate-400">Processando… {{ task.progress }}%</p>
      <p v-if="task.state === TASK_STATE_FAILED" class="text-sm text-rose-400">
        Render falhou{{ task.error ? `: ${task.error}` : '' }}
      </p>

      <div v-if="task.state === TASK_STATE_COMPLETE && task.videos?.length" class="flex flex-col gap-3">
        <video :src="task.videos[0]" controls class="w-full rounded-lg bg-black" />
        <a
          class="font-semibold text-indigo-400 no-underline hover:text-indigo-300"
          :href="task.videos[0]"
          download
        >
          Baixar vídeo
        </a>
        <RouterLink
          class="font-semibold text-indigo-400 no-underline hover:text-indigo-300"
          to="/criar/publish"
        >
          Ir para Publicar →
        </RouterLink>
      </div>
    </template>
  </div>
</template>
