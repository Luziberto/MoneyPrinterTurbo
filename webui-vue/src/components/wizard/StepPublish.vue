<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'
import { publishApi, type PublishStatus } from '../../api/publish'
import { videosApi } from '../../api/videos'
import { ApiError } from '../../api/client'
import { btnPrimaryClass } from '../../lib/cockpit-ui'

const workspaceStore = useWorkspaceStore()
const status = ref<PublishStatus | null>(null)
const selectedPlatforms = ref<string[]>([])
const videoPaths = ref<string[]>([])
const publishing = ref(false)
const errorMessage = ref<string | null>(null)
const results = ref<Record<string, unknown>[] | null>(null)

onMounted(async () => {
  status.value = await publishApi.getStatus()
  selectedPlatforms.value = workspaceStore.workspace?.publish.platforms.length
    ? workspaceStore.workspace.publish.platforms
    : status.value.platforms

  const taskId = workspaceStore.workspace?.render.last_render_task_id
  if (taskId) {
    const task = await videosApi.getTask(taskId)
    videoPaths.value = task.videos ?? []
  }
})

function togglePlatform(platform: string) {
  const index = selectedPlatforms.value.indexOf(platform)
  if (index >= 0) selectedPlatforms.value.splice(index, 1)
  else selectedPlatforms.value.push(platform)
}

async function publishNow() {
  errorMessage.value = null
  publishing.value = true
  try {
    const response = await publishApi.publish(workspaceStore.channelSlug, {
      video_paths: videoPaths.value,
      subject: workspaceStore.workspace?.script.video_subject ?? '',
      script: workspaceStore.workspace?.script.video_script ?? '',
      platforms: selectedPlatforms.value,
    })
    results.value = response.results
  } catch (err) {
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
  } finally {
    publishing.value = false
  }
}
</script>

<template>
  <div class="flex max-w-lg flex-col gap-4">
    <h2 class="text-xl font-bold tracking-tight">Publicar</h2>

    <p v-if="status && !status.configured" class="text-sm text-slate-500">
      Backend "{{ status.backend }}" não está configurado — publique manualmente por enquanto.
    </p>

    <p v-if="videoPaths.length === 0" class="text-sm text-slate-500">Nenhum vídeo renderizado ainda.</p>

    <div v-if="status" class="flex flex-wrap gap-4">
      <label
        v-for="platform in status.platforms"
        :key="platform"
        class="flex items-center gap-1.5 text-sm"
      >
        <input
          type="checkbox"
          class="accent-indigo-500"
          :checked="selectedPlatforms.includes(platform)"
          @change="togglePlatform(platform)"
        />
        <span>{{ platform }}</span>
      </label>
    </div>

    <button
      :class="btnPrimaryClass"
      :disabled="publishing || videoPaths.length === 0"
      @click="publishNow"
    >
      {{ publishing ? 'Publicando…' : 'Publicar agora' }}
    </button>

    <p v-if="errorMessage" class="text-sm text-rose-400">{{ errorMessage }}</p>

    <ul v-if="results" class="flex list-none flex-col gap-1 p-0 text-xs">
      <li v-for="(result, index) in results" :key="index">
        {{ result.success ? '✓' : '✗' }} {{ JSON.stringify(result) }}
      </li>
    </ul>
  </div>
</template>
