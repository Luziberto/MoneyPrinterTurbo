<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { channelsApi, type Topic } from '../../api/channels'
import { ApiError } from '../../api/client'
import { btnPrimaryClass } from '../../lib/cockpit-ui'
import { useChannelsStore } from '../../stores/channels'
import { useUiStore } from '../../stores/ui'
import { useWorkspaceStore } from '../../stores/workspace'

const uiStore = useUiStore()
const channelsStore = useChannelsStore()
const workspaceStore = useWorkspaceStore()

const topics = ref<Topic[]>([])
const loading = ref(false)
const errorMessage = ref<string | null>(null)

async function loadTopics() {
  if (!channelsStore.activeSlug) {
    topics.value = []
    return
  }
  loading.value = true
  errorMessage.value = null
  try {
    const result = await channelsApi.listTopics(channelsStore.activeSlug, 'pending')
    topics.value = result.topics
  } catch (err) {
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

async function useTopic(topic: Topic) {
  if (!channelsStore.activeSlug) return
  await channelsApi.loadTopicIntoWorkspace(channelsStore.activeSlug, topic.uid)
  await workspaceStore.load(channelsStore.activeSlug)
}

onMounted(() => {
  void loadTopics()
})

watch(() => channelsStore.activeSlug, () => {
  void loadTopics()
})
</script>

<template>
  <aside
    class="flex w-full flex-col overflow-hidden rounded-xl border border-slate-600/20 bg-slate-900/45 light:border-slate-200 light:bg-white light:shadow-sm light:shadow-slate-200/50"
    aria-label="Topics queue"
  >
    <header class="shrink-0 border-b border-slate-600/20 px-4 py-2.5 light:border-slate-200">
      <h3 class="cockpit-title text-sm font-bold">{{ uiStore.tr('Cockpit Topics Queue Title') }}</h3>
      <p class="cockpit-muted mt-0.5 text-xs">{{ uiStore.tr('Cockpit Topics Queue Hint') }}</p>
      <p v-if="topics.length > 0" class="cockpit-subtle mt-1.5 text-[0.65rem]">
        {{ topics.length }} {{ uiStore.tr('Cockpit Topics Pending').toLowerCase() }}
      </p>
    </header>

    <div
      class="topics-queue-body max-h-128 min-h-0 overflow-y-auto overscroll-contain px-3 py-2"
    >
      <p v-if="errorMessage" class="px-1 py-2 text-xs text-rose-400">{{ errorMessage }}</p>
      <p v-else-if="loading" class="cockpit-muted px-1 py-2 text-xs">{{ uiStore.tr('Cockpit Loading') }}</p>
      <p v-else-if="topics.length === 0" class="cockpit-muted px-1 py-2 text-xs">
        {{ uiStore.tr('Cockpit No Topics') }}
      </p>

      <ul v-else class="flex list-none flex-col gap-2 p-0">
        <li
          v-for="topic in topics"
          :key="topic.uid"
          class="rounded-lg border border-slate-600/20 bg-cockpit-surface/50 p-2.5 light:border-slate-200 light:bg-slate-50"
        >
          <div class="mb-1.5 flex items-start justify-between gap-2">
            <span
              class="shrink-0 rounded bg-amber-500/15 px-1.5 py-0.5 text-[0.62rem] font-bold tracking-wide text-amber-300 uppercase light:text-amber-700"
            >
              {{ topic.category }}
            </span>
            <span class="cockpit-muted text-[0.62rem]">#{{ topic.id }}</span>
          </div>
          <p class="cockpit-title mb-2 line-clamp-2 text-sm leading-snug">{{ topic.topic }}</p>
          <button
            type="button"
            :class="[btnPrimaryClass, 'w-full py-1.5 text-xs']"
            @click="useTopic(topic)"
          >
            {{ uiStore.tr('Cockpit Use Topic In Create') }}
          </button>
        </li>
      </ul>
    </div>
  </aside>
</template>
