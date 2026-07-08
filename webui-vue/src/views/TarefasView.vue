<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { cockpitApi, type RuntimeLimits } from '../api/cockpit'
import { videosApi, TASK_STATE_COMPLETE, TASK_STATE_FAILED, type TaskState } from '../api/videos'

const runtimeLimits = ref<RuntimeLimits | null>(null)
const tasks = ref<TaskState[]>([])
let runtimeTimer: ReturnType<typeof setInterval> | null = null
let tasksTimer: ReturnType<typeof setInterval> | null = null

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

async function clearLock(force: boolean) {
  await cockpitApi.clearGenerationLock(force)
  await refreshRuntimeLimits()
}

async function removeTask(taskId: string) {
  await videosApi.deleteTask(taskId)
  await refreshTasks()
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

onMounted(() => {
  void refreshRuntimeLimits()
  void refreshTasks()
  runtimeTimer = setInterval(refreshRuntimeLimits, 5000)
  tasksTimer = setInterval(refreshTasks, 5000)
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onUnmounted(() => {
  if (runtimeTimer) clearInterval(runtimeTimer)
  if (tasksTimer) clearInterval(tasksTimer)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>

<template>
  <div class="tarefas">
    <h2>Tarefas</h2>

    <section v-if="runtimeLimits" class="runtime">
      <h3>Runtime</h3>
      <div class="runtime__grid">
        <span>Threads máx: {{ runtimeLimits.max_threads }}</span>
        <span>Downloads máx/task: {{ runtimeLimits.max_downloads_per_task }}</span>
        <span>Vídeo remoto máx: {{ runtimeLimits.max_remote_video_mb }}MB</span>
      </div>
      <div v-if="runtimeLimits.lock" class="lock-banner">
        <span>🔒 Geração em andamento (task {{ runtimeLimits.lock.task_id }})</span>
        <button @click="clearLock(false)">Limpar se obsoleto</button>
        <button class="danger" @click="clearLock(true)">Forçar limpeza</button>
      </div>
      <p v-else class="hint">Nenhuma geração em andamento.</p>
    </section>

    <section class="tasks">
      <h3>Tarefas recentes</h3>
      <p v-if="tasks.length === 0" class="hint">Nenhuma tarefa ainda.</p>
      <ul v-else>
        <li v-for="task in tasks" :key="task.task_id" class="task" :class="`task--${taskLabel(task.state)}`">
          <span class="task__id">{{ task.task_id }}</span>
          <span class="task__state">{{ taskLabel(task.state) }} ({{ task.progress }}%)</span>
          <button class="danger" @click="removeTask(task.task_id)">Remover</button>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.tarefas {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  max-width: 40rem;
}

h3 {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
}

.runtime__grid {
  display: flex;
  gap: 1.5rem;
  font-size: 0.85rem;
  color: var(--cockpit-text-muted);
  margin-bottom: 0.75rem;
}

.hint {
  color: var(--cockpit-text-muted);
  font-size: 0.85rem;
}

.lock-banner {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.6rem 0.9rem;
  border-radius: 0.5rem;
  background: var(--cockpit-surface-hover);
  font-size: 0.85rem;
}

.lock-banner button,
.task button {
  padding: 0.3rem 0.6rem;
  border-radius: 0.4rem;
  border: none;
  background: var(--cockpit-accent);
  color: var(--cockpit-accent-contrast);
  font-size: 0.78rem;
  font-weight: 600;
}

button.danger {
  background: var(--cockpit-danger);
  color: white;
}

.tasks ul {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.task {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.8rem;
  border: 1px solid var(--cockpit-border);
  border-radius: 0.4rem;
  font-size: 0.82rem;
}

.task__id {
  font-family: ui-monospace, monospace;
  color: var(--cockpit-text-muted);
  flex: 1;
}

.task--falhou .task__state {
  color: var(--cockpit-danger);
}

.task--concluído .task__state {
  color: var(--cockpit-success);
}
</style>
