<script setup lang="ts">
import { PUBLISH_PLATFORMS } from '../../api/videoLibrary'

const props = withDefaults(
  defineProps<{ modelValue: string[]; availablePlatforms?: readonly string[] }>(),
  { availablePlatforms: () => PUBLISH_PLATFORMS },
)
const emit = defineEmits<{ 'update:modelValue': [platforms: string[]] }>()

function toggle(platform: string) {
  const next = props.modelValue.includes(platform)
    ? props.modelValue.filter((p) => p !== platform)
    : [...props.modelValue, platform]
  emit('update:modelValue', next)
}
</script>

<template>
  <div class="flex flex-wrap gap-3">
    <label
      v-for="platform in availablePlatforms"
      :key="platform"
      class="flex items-center gap-1.5 rounded-lg border border-slate-600/25 bg-cockpit-surface/60 px-3 py-2 text-sm capitalize light:border-slate-200 light:bg-white"
    >
      <input
        type="checkbox"
        class="accent-indigo-500"
        :checked="modelValue.includes(platform)"
        @change="toggle(platform)"
      />
      {{ platform }}
    </label>
  </div>
</template>
