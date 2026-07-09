<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useChannelsStore } from '../../stores/channels'
import { channelsApi, type Topic } from '../../api/channels'
import { ApiError } from '../../api/client'
import { cardClass, selectClass } from '../../lib/cockpit-ui'
import { useUiStore } from '../../stores/ui'

const uiStore = useUiStore()
const channelsStore = useChannelsStore()
const topics = ref<Topic[]>([])
const counts = ref<Record<string, number>>({})
const statusFilter = ref('used')
const loading = ref(false)
const errorMessage = ref<string | null>(null)

const USED_STATUSES = new Set(['generated', 'approved', 'published', 'processing'])

const filterOptions = computed(() => [
  { value: 'used', label: uiStore.tr('Cockpit Topics Used') },
  { value: 'generated', label: uiStore.tr('Cockpit Topics Generated') },
  { value: 'approved', label: uiStore.tr('Cockpit Topics Approved') },
  { value: 'published', label: uiStore.tr('Cockpit Topics Published') },
  { value: 'failed', label: uiStore.tr('Cockpit Topics Failed') },
  { value: 'all', label: uiStore.tr('Cockpit History All Non Pending') },
])

const visibleTopics = computed(() => {
  const list = topics.value.filter((t) => t.status !== 'pending')
  if (statusFilter.value === 'used') {
    return list.filter((t) => USED_STATUSES.has(t.status))
  }
  if (statusFilter.value === 'all') {
    return list
  }
  return list.filter((t) => t.status === statusFilter.value)
})

function statusBadgeClass(status: string) {
  if (status === 'published' || status === 'approved') return 'text-emerald-400'
  if (status === 'failed') return 'text-rose-400'
  if (status === 'generated' || status === 'processing') return 'text-sky-400'
  return 'cockpit-muted'
}

async function loadTopics() {
  if (!channelsStore.activeSlug) return
  loading.value = true
  errorMessage.value = null
  try {
    const result = await channelsApi.listTopics(channelsStore.activeSlug, 'all')
    topics.value = result.topics
    counts.value = result.counts
  } catch (err) {
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

onMounted(loadTopics)
watch(() => channelsStore.activeSlug, loadTopics)
</script>

<template>
  <div class="flex w-full flex-col gap-4">
    <div class="flex flex-wrap items-center gap-4">
      <h3 class="cockpit-title text-sm font-bold">{{ uiStore.tr('Cockpit Tab History') }}</h3>
      <select v-model="statusFilter" :class="selectClass">
        <option v-for="opt in filterOptions" :key="opt.value" :value="opt.value">
          {{ opt.label }}
        </option>
      </select>
      <span class="flex flex-wrap gap-3 text-xs text-slate-500 light:text-slate-600">
        <span v-for="(count, status) in counts" :key="status">{{ status }}: {{ count }}</span>
      </span>
    </div>

    <p v-if="errorMessage" class="text-sm text-rose-400">{{ errorMessage }}</p>
    <p v-else-if="loading" class="cockpit-muted text-sm">{{ uiStore.tr('Cockpit Loading') }}</p>
    <p v-else-if="visibleTopics.length === 0" class="cockpit-muted text-sm">
      {{ uiStore.tr('Cockpit History Empty') }}
    </p>

    <ul v-else class="grid list-none grid-cols-1 gap-3 p-0 sm:grid-cols-2 xl:grid-cols-3">
      <li
        v-for="topic in visibleTopics"
        :key="topic.uid"
        :class="[cardClass, 'flex h-full flex-col gap-3']"
      >
        <div class="flex items-center justify-between gap-2 text-xs">
          <span class="cockpit-muted font-bold uppercase tracking-wide">{{ topic.category }}</span>
          <span :class="statusBadgeClass(topic.status)" class="font-semibold capitalize">
            {{ topic.status }}
          </span>
        </div>
        <p class="cockpit-title flex-1 text-sm leading-snug">{{ topic.topic }}</p>
        <div class="cockpit-muted space-y-0.5 text-xs">
          <p v-if="topic.generated_at">#{{ topic.id }} · {{ topic.generated_at }}</p>
          <p v-else>#{{ topic.id }}</p>
          <RouterLink v-if="topic.task_id" :to="`/videos/${topic.task_id}`" class="block truncate font-mono no-underline">
            task: {{ topic.task_id }}
          </RouterLink>
        </div>
      </li>
    </ul>
  </div>
</template>
