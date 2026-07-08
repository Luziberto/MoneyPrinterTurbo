<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'
import { publishApi, type PublishStatus } from '../../api/publish'
import { videosApi } from '../../api/videos'
import { ApiError } from '../../api/client'

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
  <div class="step-publish">
    <h2>Publicar</h2>

    <p v-if="status && !status.configured" class="hint">
      Backend "{{ status.backend }}" não está configurado -- publique manualmente por enquanto.
    </p>

    <p v-if="videoPaths.length === 0" class="hint">Nenhum vídeo renderizado ainda.</p>

    <div v-if="status" class="platforms">
      <label v-for="platform in status.platforms" :key="platform" class="checkbox">
        <input
          type="checkbox"
          :checked="selectedPlatforms.includes(platform)"
          @change="togglePlatform(platform)"
        />
        <span>{{ platform }}</span>
      </label>
    </div>

    <button :disabled="publishing || videoPaths.length === 0" @click="publishNow">
      {{ publishing ? 'Publicando…' : 'Publicar agora' }}
    </button>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>

    <ul v-if="results" class="results">
      <li v-for="(result, index) in results" :key="index">
        {{ result.success ? '✓' : '✗' }} {{ JSON.stringify(result) }}
      </li>
    </ul>
  </div>
</template>

<style scoped>
.step-publish {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 32rem;
}

.hint {
  color: var(--cockpit-text-muted);
  font-size: 0.85rem;
}

.platforms {
  display: flex;
  gap: 1rem;
}

.checkbox {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
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

.results {
  list-style: none;
  padding: 0;
  font-size: 0.8rem;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
</style>
