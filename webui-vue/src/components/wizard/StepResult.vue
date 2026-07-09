<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'
import { videosApi, TASK_STATE_COMPLETE, TASK_STATE_FAILED, type TaskState } from '../../api/videos'
import { useWizardNavigation } from '../../composables/useWizardNavigation'
import { btnPrimaryClass } from '../../lib/cockpit-ui'
import { useUiStore } from '../../stores/ui'

const workspaceStore = useWorkspaceStore()
const navigate = useWizardNavigation()
const uiStore = useUiStore()
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

async function createAnother() {
  await workspaceStore.reset()
  navigate('script')
}
</script>

<template>
  <div class="flex max-w-96 flex-col gap-4">
    <h2 class="text-xl font-bold tracking-tight">{{ uiStore.tr('Cockpit Step Result Title') }}</h2>

    <p v-if="!taskId" class="text-sm text-slate-500">
      {{ uiStore.tr('Cockpit Step Result Empty') }}
    </p>

    <template v-else-if="task">
      <p class="text-sm"><strong>Task:</strong> {{ taskId }}</p>
      <p v-if="!isDone" class="text-sm text-slate-400">{{ uiStore.tr('Cockpit Step Result Processing') }} {{ task.progress }}%</p>
      <p v-if="task.state === TASK_STATE_FAILED" class="text-sm text-rose-400">
        {{ uiStore.tr('Cockpit Step Result Failed') }}{{ task.error ? `: ${task.error}` : '' }}
      </p>

      <div v-if="task.state === TASK_STATE_COMPLETE && task.videos?.length" class="flex flex-col gap-3">
        <video :src="task.videos[0]" controls class="w-full rounded-lg bg-black" />

        <div class="flex flex-wrap gap-2.5">
          <RouterLink :class="btnPrimaryClass" :to="`/videos/${taskId}`">
            {{ uiStore.tr('Cockpit Step Result Open Video') }}
          </RouterLink>
          <RouterLink
            class="inline-flex items-center justify-center rounded-lg border border-slate-600/30 bg-slate-800/80 px-4 py-2.5 text-sm font-semibold text-slate-100 no-underline transition hover:bg-slate-700"
            to="/videos"
          >
            {{ uiStore.tr('Cockpit Step Result Go To Library') }}
          </RouterLink>
          <button
            type="button"
            class="inline-flex items-center justify-center rounded-lg border border-slate-600/30 bg-transparent px-4 py-2.5 text-sm font-semibold text-slate-300 transition hover:bg-slate-800/60"
            @click="createAnother"
          >
            {{ uiStore.tr('Cockpit Step Result Create Another') }}
          </button>
        </div>
      </div>
    </template>
  </div>
</template>
