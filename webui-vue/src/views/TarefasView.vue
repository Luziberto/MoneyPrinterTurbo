<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { cockpitApi, type RuntimeLimits } from '../api/cockpit'
import { videosApi, TASK_STATE_COMPLETE, TASK_STATE_FAILED, type TaskState } from '../api/videos'
import { videoLibraryApi, type VideoPublication } from '../api/videoLibrary'
import { btnPrimaryClass, cardClass } from '../lib/cockpit-ui'
import { useUiStore } from '../stores/ui'
import { useWorkspaceStore } from '../stores/workspace'

const uiStore = useUiStore()
const workspaceStore = useWorkspaceStore()

const runtimeLimits = ref<RuntimeLimits | null>(null)
const tasks = ref<TaskState[]>([])
const pendingUploads = ref<(VideoPublication & { videoTitle: string })[]>([])
const uploadsLoading = ref(false)
let runtimeTimer: ReturnType<typeof setInterval> | null = null
let tasksTimer: ReturnType<typeof setInterval> | null = null
let uploadsTimer: ReturnType<typeof setInterval> | null = null

const btnDangerClass =
  'rounded-lg bg-rose-500 px-2.5 py-1.5 text-xs font-semibold text-white transition hover:bg-rose-600 disabled:opacity-55'

function taskLabel(state: number): string {
  if (state === TASK_STATE_COMPLETE) return 'concluído'
  if (state === TASK_STATE_FAILED) return 'falhou'
  return 'processando'
}

async function refreshRuntimeLimits() {
  runtimeLimits.value = await cockpitApi.getRuntimeLimits()
}

async function refreshTasks() {
  const result = await videosApi.listTasks(1, 20)
  tasks.value = result.tasks
}

async function refreshUploads() {
  uploadsLoading.value = true
  try {
    const { videos } = await videoLibraryApi.list({ status: 'scheduled', page_size: 15 })
    const details = await Promise.all(videos.map((v) => videoLibraryApi.get(v.id)))
    pendingUploads.value = details.flatMap((detail) =>
      detail.publications
        .filter((pub) => pub.status === 'scheduled' || pub.status === 'publishing')
        .map((pub) => ({ ...pub, videoTitle: detail.title || detail.subject || detail.id })),
    )
  } finally {
    uploadsLoading.value = false
  }
}

async function clearLock(force: boolean) {
  await cockpitApi.clearGenerationLock(force)
  await refreshRuntimeLimits()
}

async function removeTask(taskId: string) {
  await videosApi.deleteTask(taskId)
  await refreshTasks()
}

async function cancelUpload(pub: VideoPublication) {
  await videoLibraryApi.cancelPublication(pub.video_id, pub.id)
  await refreshUploads()
}

function handleVisibilityChange() {
  if (document.hidden) {
    if (tasksTimer) clearInterval(tasksTimer)
    tasksTimer = null
  } else if (!tasksTimer) {
    tasksTimer = setInterval(refreshTasks, 5000)
    void refreshTasks()
  }
}

const collectorJob = computed(() => workspaceStore.workspace?.media.last_collector_job ?? null)

onMounted(() => {
  void refreshRuntimeLimits()
  void refreshTasks()
  void refreshUploads()
  runtimeTimer = setInterval(refreshRuntimeLimits, 5000)
  tasksTimer = setInterval(refreshTasks, 5000)
  uploadsTimer = setInterval(refreshUploads, 15000)
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onUnmounted(() => {
  if (runtimeTimer) clearInterval(runtimeTimer)
  if (tasksTimer) clearInterval(tasksTimer)
  if (uploadsTimer) clearInterval(uploadsTimer)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>

<template>
  <div class="flex max-w-[42rem] flex-col gap-6">
    <h2 class="text-xl font-bold tracking-tight">{{ uiStore.tr('Cockpit Tab Tasks') }}</h2>

    <!-- Fila -->
    <section v-if="runtimeLimits" :class="cardClass">
      <h3 class="mb-2 text-sm font-semibold">{{ uiStore.tr('Cockpit Tarefas Queue') }}</h3>
      <div class="mb-3 flex flex-wrap gap-6 text-sm text-slate-500">
        <span>Threads máx: {{ runtimeLimits.max_threads }}</span>
        <span>Downloads máx/task: {{ runtimeLimits.max_downloads_per_task }}</span>
        <span>Vídeo remoto máx: {{ runtimeLimits.max_remote_video_mb }}MB</span>
      </div>
      <div
        v-if="runtimeLimits.lock"
        class="flex flex-wrap items-center gap-2.5 rounded-lg bg-slate-800/80 px-3.5 py-2.5 text-sm"
      >
        <span>🔒 Geração em andamento (task {{ runtimeLimits.lock.task_id }})</span>
        <button :class="[btnPrimaryClass, 'text-xs']" @click="clearLock(false)">
          Limpar se obsoleto
        </button>
        <button :class="btnDangerClass" @click="clearLock(true)">Forçar limpeza</button>
      </div>
      <p v-else class="text-sm text-slate-500">Nenhuma geração em andamento.</p>
    </section>

    <!-- Renderizações -->
    <section :class="cardClass">
      <h3 class="mb-2 text-sm font-semibold">{{ uiStore.tr('Cockpit Tarefas Renders') }}</h3>
      <p v-if="tasks.length === 0" class="text-sm text-slate-500">Nenhuma tarefa ainda.</p>
      <ul v-else class="flex list-none flex-col gap-1.5 p-0">
        <li
          v-for="task in tasks"
          :key="task.task_id"
          class="flex items-center gap-3 rounded-lg border border-slate-600/20 px-3 py-2 text-sm"
        >
          <span class="flex-1 font-mono text-slate-500">{{ task.task_id }}</span>
          <span
            :class="{
              'text-rose-400': taskLabel(task.state) === 'falhou',
              'text-emerald-400': taskLabel(task.state) === 'concluído',
            }"
          >
            {{ taskLabel(task.state) }} ({{ task.progress }}%)
          </span>
          <button :class="btnDangerClass" @click="removeTask(task.task_id)">Remover</button>
        </li>
      </ul>
    </section>

    <!-- Uploads -->
    <section :class="cardClass">
      <h3 class="mb-2 text-sm font-semibold">{{ uiStore.tr('Cockpit Tarefas Uploads') }}</h3>
      <p v-if="uploadsLoading && pendingUploads.length === 0" class="text-sm text-slate-500">
        {{ uiStore.tr('Cockpit Loading') }}
      </p>
      <p v-else-if="pendingUploads.length === 0" class="text-sm text-slate-500">
        {{ uiStore.tr('Cockpit Tarefas Uploads Empty') }}
      </p>
      <ul v-else class="flex list-none flex-col gap-1.5 p-0">
        <li
          v-for="pub in pendingUploads"
          :key="pub.id"
          class="flex items-center gap-3 rounded-lg border border-slate-600/20 px-3 py-2 text-sm"
        >
          <RouterLink :to="`/videos/${pub.video_id}`" class="flex-1 truncate no-underline">
            {{ pub.videoTitle }} · <span class="capitalize">{{ pub.platform }}</span>
          </RouterLink>
          <span class="text-xs text-sky-400 capitalize">{{ pub.status }}</span>
          <button :class="btnDangerClass" @click="cancelUpload(pub)">
            {{ uiStore.tr('Cockpit Videos Cancel Publication') }}
          </button>
        </li>
      </ul>
    </section>

    <!-- Collector -->
    <section :class="cardClass">
      <h3 class="mb-2 text-sm font-semibold">{{ uiStore.tr('Cockpit Tarefas Collector') }}</h3>
      <div v-if="collectorJob" class="flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-500">
        <span>{{ uiStore.tr('Cockpit Tarefas Collector Status') }}: {{ collectorJob.status }}</span>
        <span>{{ collectorJob.selected_clips_count }}/{{ collectorJob.target_clips }} clips</span>
        <span>{{ uiStore.tr('Cockpit Tarefas Collector Reused') }}: {{ collectorJob.local_reused }}</span>
        <span>{{ uiStore.tr('Cockpit Tarefas Collector New') }}: {{ collectorJob.new_downloads }}</span>
      </div>
      <p v-else class="text-sm text-slate-500">{{ uiStore.tr('Cockpit Tarefas Collector Empty') }}</p>
    </section>
  </div>
</template>
