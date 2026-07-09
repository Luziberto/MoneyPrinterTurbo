<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Bar } from 'vue-chartjs'
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip,
} from 'chart.js'
import { dashboardSummaryApi, type DashboardSummary } from '../api/dashboard'
import { ApiError } from '../api/client'
import { cardClass } from '../lib/cockpit-ui'
import { useUiStore } from '../stores/ui'
import {
  Clock,
  Film,
  FolderOpen,
  HardDrive,
  Radio,
  Send,
  Settings,
  Sparkles,
  TriangleAlert,
  Video,
} from '../lib/cockpit-icons'

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend)

const uiStore = useUiStore()

const summary = ref<DashboardSummary | null>(null)
const loading = ref(false)
const errorMessage = ref<string | null>(null)

const STATUS_ORDER = ['draft', 'rendering', 'ready', 'scheduled', 'published', 'archived', 'failed'] as const

const STAGE_LABELS: Record<string, string> = {
  script: 'Roteiro',
  terms: 'Termos',
  tts: 'TTS',
  collector: 'Coletor',
  render: 'Render',
  upload: 'Upload',
}

const quickActions = [
  { to: '/criar', icon: Sparkles, key: 'Cockpit Dashboard Quick Create' },
  { to: '/videos', icon: Video, key: 'Cockpit Dashboard Quick Videos' },
  { to: '/tarefas', icon: FolderOpen, key: 'Cockpit Dashboard Quick Tasks' },
  { to: '/canais', icon: Radio, key: 'Cockpit Dashboard Quick Channels' },
  { to: '/configuracoes', icon: Settings, key: 'Cockpit Dashboard Quick Settings' },
]

async function load() {
  loading.value = true
  errorMessage.value = null
  try {
    summary.value = await dashboardSummaryApi.get()
  } catch (err) {
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

onMounted(load)

const stageChartData = computed(() => {
  const timing = summary.value?.stage_timing_avg_seconds ?? {}
  const stages = Object.keys(STAGE_LABELS).filter((s) => timing[s] != null)
  return {
    labels: stages.map((s) => STAGE_LABELS[s]),
    datasets: [
      {
        label: 'segundos',
        data: stages.map((s) => timing[s] ?? 0),
        backgroundColor: 'rgba(129, 140, 248, 0.6)',
        borderRadius: 6,
      },
    ],
  }
})

const stageChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: { y: { beginAtZero: true } },
}

function diskUsedPct(disk: DashboardSummary['disk_usage'] | undefined) {
  if (!disk || !disk.total) return 0
  return Math.round((disk.used / disk.total) * 100)
}

function formatBytes(bytes: number) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let value = bytes
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024
    i += 1
  }
  return `${value.toFixed(1)} ${units[i]}`
}

function statusLabel(status: string) {
  const key = `Cockpit Video Status ${status.charAt(0).toUpperCase()}${status.slice(1)}`
  const translated = uiStore.tr(key)
  return translated === key ? status : translated
}
</script>

<template>
  <div class="flex w-full flex-col gap-5">
    <div>
      <h2 class="cockpit-heading text-xl font-bold tracking-tight">
        {{ uiStore.tr('Cockpit Tab Dashboard') }}
      </h2>
      <p class="cockpit-muted mt-1 text-sm">{{ uiStore.tr('Cockpit Dashboard Tagline') }}</p>
    </div>

    <p v-if="errorMessage" class="text-sm text-rose-400">{{ errorMessage }}</p>

    <!-- Quick actions -->
    <section class="flex flex-wrap gap-2">
      <RouterLink
        v-for="action in quickActions"
        :key="action.to"
        :to="action.to"
        class="flex items-center gap-2 rounded-xl border border-slate-600/25 bg-cockpit-surface/75 px-4 py-2.5 text-sm font-semibold text-slate-300 no-underline transition hover:border-indigo-400/40 hover:bg-indigo-500/10 hover:text-indigo-300 light:border-slate-200 light:bg-white light:text-slate-700 light:hover:bg-indigo-50 light:hover:text-indigo-600"
      >
        <component :is="action.icon" :size="15" />
        {{ uiStore.tr(action.key) }}
      </RouterLink>
    </section>

    <!-- Time-window cards -->
    <section class="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <div :class="cardClass">
        <p class="cockpit-muted text-xs font-bold tracking-wide uppercase">
          {{ uiStore.tr('Cockpit Dashboard Today') }}
        </p>
        <p class="cockpit-title mt-1 text-2xl font-bold">
          {{ summary?.time_window_counts.today ?? '—' }}
        </p>
      </div>
      <div :class="cardClass">
        <p class="cockpit-muted text-xs font-bold tracking-wide uppercase">
          {{ uiStore.tr('Cockpit Dashboard This Week') }}
        </p>
        <p class="cockpit-title mt-1 text-2xl font-bold">
          {{ summary?.time_window_counts.this_week ?? '—' }}
        </p>
      </div>
      <div :class="cardClass">
        <p class="cockpit-muted text-xs font-bold tracking-wide uppercase">
          {{ uiStore.tr('Cockpit Dashboard This Month') }}
        </p>
        <p class="cockpit-title mt-1 text-2xl font-bold">
          {{ summary?.time_window_counts.this_month ?? '—' }}
        </p>
      </div>
    </section>

    <!-- Status counts -->
    <section :class="cardClass">
      <h3 class="cockpit-title mb-3 text-sm font-bold">{{ uiStore.tr('Cockpit Dashboard Video Statuses') }}</h3>
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
        <div v-for="status in STATUS_ORDER" :key="status" class="text-center">
          <p class="cockpit-title text-xl font-bold">
            {{ summary?.status_counts[status] ?? 0 }}
          </p>
          <p class="cockpit-muted text-[0.68rem] tracking-wide uppercase">{{ statusLabel(status) }}</p>
        </div>
      </div>
    </section>

    <div class="grid grid-cols-1 gap-5 lg:grid-cols-2">
      <!-- Stage timing -->
      <section :class="cardClass">
        <h3 class="cockpit-title mb-3 flex items-center gap-2 text-sm font-bold">
          <Clock :size="15" />
          {{ uiStore.tr('Cockpit Dashboard Stage Timing') }}
        </h3>
        <div v-if="stageChartData.labels.length" class="h-48">
          <Bar :data="stageChartData" :options="stageChartOptions" />
        </div>
        <p v-else class="cockpit-muted text-sm">{{ uiStore.tr('Cockpit Dashboard No Data') }}</p>
      </section>

      <!-- Estimated time saved + disk usage -->
      <section class="flex flex-col gap-4">
        <div :class="cardClass">
          <h3 class="cockpit-title mb-2 flex items-center gap-2 text-sm font-bold">
            <Sparkles :size="15" />
            {{ uiStore.tr('Cockpit Dashboard Time Saved') }}
          </h3>
          <p class="cockpit-title text-2xl font-bold">
            {{ Math.round(summary?.estimated_minutes_saved.minutes ?? 0) }} min
          </p>
          <p class="cockpit-muted mt-1 text-xs">{{ uiStore.tr('Cockpit Dashboard Time Saved Estimate Note') }}</p>
        </div>
        <div :class="cardClass">
          <h3 class="cockpit-title mb-2 flex items-center gap-2 text-sm font-bold">
            <HardDrive :size="15" />
            {{ uiStore.tr('Cockpit Dashboard Disk Usage') }}
          </h3>
          <div class="h-2 w-full overflow-hidden rounded-full bg-slate-700/40 light:bg-slate-200">
            <div
              class="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-600"
              :style="{ width: `${diskUsedPct(summary?.disk_usage)}%` }"
            />
          </div>
          <p class="cockpit-muted mt-2 text-xs">
            {{ formatBytes(summary?.disk_usage.used ?? 0) }} / {{ formatBytes(summary?.disk_usage.total ?? 0) }}
            ({{ diskUsedPct(summary?.disk_usage) }}%)
          </p>
        </div>
      </section>
    </div>

    <div class="grid grid-cols-1 gap-5 lg:grid-cols-2">
      <!-- Recent videos -->
      <section :class="cardClass">
        <h3 class="cockpit-title mb-3 flex items-center gap-2 text-sm font-bold">
          <Film :size="15" />
          {{ uiStore.tr('Cockpit Dashboard Recent Videos') }}
        </h3>
        <ul v-if="summary?.recent_videos.length" class="flex list-none flex-col gap-2 p-0">
          <li
            v-for="video in summary.recent_videos"
            :key="video.id"
            class="flex items-center justify-between gap-2 rounded-lg border border-slate-600/15 px-3 py-2 text-sm light:border-slate-200"
          >
            <RouterLink :to="`/videos/${video.id}`" class="min-w-0 truncate no-underline">
              <span class="cockpit-title">{{ video.title || video.subject || video.id }}</span>
            </RouterLink>
            <span class="cockpit-muted shrink-0 text-xs">{{ statusLabel(video.status) }}</span>
          </li>
        </ul>
        <p v-else class="cockpit-muted text-sm">{{ uiStore.tr('Cockpit Dashboard No Data') }}</p>
      </section>

      <!-- Recent errors -->
      <section :class="cardClass">
        <h3 class="cockpit-title mb-3 flex items-center gap-2 text-sm font-bold">
          <TriangleAlert :size="15" class="text-rose-400" />
          {{ uiStore.tr('Cockpit Dashboard Recent Errors') }}
        </h3>
        <ul v-if="summary?.recent_errors.length" class="flex list-none flex-col gap-2 p-0">
          <li
            v-for="video in summary.recent_errors"
            :key="video.id"
            class="rounded-lg border border-rose-500/20 px-3 py-2 text-sm light:border-rose-300/40"
          >
            <RouterLink :to="`/videos/${video.id}`" class="cockpit-title truncate no-underline">
              {{ video.title || video.subject || video.id }}
            </RouterLink>
            <p class="mt-0.5 truncate text-xs text-rose-400">{{ video.error }}</p>
          </li>
        </ul>
        <p v-else class="cockpit-muted text-sm">{{ uiStore.tr('Cockpit Dashboard No Data') }}</p>
      </section>
    </div>

    <!-- Queue summary -->
    <section :class="cardClass">
      <h3 class="cockpit-title mb-2 flex items-center gap-2 text-sm font-bold">
        <Send :size="15" />
        {{ uiStore.tr('Cockpit Dashboard Queue') }}
      </h3>
      <p class="cockpit-muted text-sm">
        {{ uiStore.tr('Cockpit Dashboard Queue Total Tasks') }}: {{ summary?.queue.total_tasks ?? 0 }}
      </p>
      <p v-if="summary?.queue.lock" class="mt-1 text-xs text-amber-400">
        {{ uiStore.tr('Cockpit Dashboard Queue Lock Active') }}
      </p>
    </section>
  </div>
</template>
