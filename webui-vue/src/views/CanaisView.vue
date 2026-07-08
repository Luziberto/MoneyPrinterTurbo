<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useChannelsStore } from '../stores/channels'
import { useWorkspaceStore } from '../stores/workspace'
import { channelsApi, type Topic } from '../api/channels'
import { ApiError } from '../api/client'

const channelsStore = useChannelsStore()
const workspaceStore = useWorkspaceStore()
const topics = ref<Topic[]>([])
const counts = ref<Record<string, number>>({})
const statusFilter = ref('pending')
const loading = ref(false)
const errorMessage = ref<string | null>(null)

async function loadTopics() {
  if (!channelsStore.activeSlug) return
  loading.value = true
  errorMessage.value = null
  try {
    const result = await channelsApi.listTopics(channelsStore.activeSlug, statusFilter.value)
    topics.value = result.topics
    counts.value = result.counts
  } catch (err) {
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

async function loadIntoWorkspace(topic: Topic) {
  if (!channelsStore.activeSlug) return
  await channelsApi.loadTopicIntoWorkspace(channelsStore.activeSlug, topic.uid)
  await workspaceStore.load(channelsStore.activeSlug)
}

onMounted(async () => {
  await channelsStore.fetchChannels()
  await loadTopics()
})

watch([() => channelsStore.activeSlug, statusFilter], loadTopics)
</script>

<template>
  <div class="canais">
    <h2>Canais</h2>

    <div class="toolbar">
      <select v-model="statusFilter">
        <option value="pending">Pendentes</option>
        <option value="generated">Gerados</option>
        <option value="approved">Aprovados</option>
        <option value="published">Publicados</option>
        <option value="failed">Falhados</option>
        <option value="all">Todos</option>
      </select>
      <span class="counts">
        <span v-for="(count, status) in counts" :key="status">{{ status }}: {{ count }}</span>
      </span>
    </div>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
    <p v-else-if="loading" class="hint">Carregando…</p>
    <p v-else-if="topics.length === 0" class="hint">Nenhum tópico encontrado.</p>

    <ul v-else class="topics">
      <li v-for="topic in topics" :key="topic.uid" class="topic">
        <div class="topic__body">
          <span class="topic__category">{{ topic.category }}</span>
          <span class="topic__text">{{ topic.topic }}</span>
        </div>
        <button @click="loadIntoWorkspace(topic)">Usar no Criar</button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.canais {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 40rem;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 1rem;
}

select {
  padding: 0.4rem 0.6rem;
  border-radius: 0.4rem;
  border: 1px solid var(--cockpit-border);
  background: var(--cockpit-surface);
  color: var(--cockpit-text);
}

.counts {
  display: flex;
  gap: 0.75rem;
  font-size: 0.8rem;
  color: var(--cockpit-text-muted);
}

.hint {
  color: var(--cockpit-text-muted);
  font-size: 0.85rem;
}

.error {
  color: var(--cockpit-danger);
  font-size: 0.85rem;
}

.topics {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.topic {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.6rem 0.9rem;
  border: 1px solid var(--cockpit-border);
  border-radius: 0.5rem;
}

.topic__body {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.topic__category {
  font-size: 0.7rem;
  text-transform: uppercase;
  color: var(--cockpit-text-muted);
}

.topic button {
  padding: 0.4rem 0.75rem;
  border-radius: 0.4rem;
  border: none;
  background: var(--cockpit-accent);
  color: var(--cockpit-accent-contrast);
  font-weight: 600;
  font-size: 0.8rem;
  white-space: nowrap;
}
</style>
