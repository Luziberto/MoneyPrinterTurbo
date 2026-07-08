<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { configApi, type ConfigSnapshot } from '../api/config'
import { ApiError } from '../api/client'

const config = ref<ConfigSnapshot | null>(null)
const saving = ref(false)
const errorMessage = ref<string | null>(null)
const savedAt = ref<string | null>(null)

onMounted(async () => {
  config.value = await configApi.get()
})

function field(section: keyof ConfigSnapshot, key: string): string {
  const value = config.value?.[section]?.[key]
  return value === undefined || value === null ? '' : String(value)
}

function setField(section: keyof ConfigSnapshot, key: string, value: string) {
  if (!config.value) return
  config.value[section][key] = value
}

async function save() {
  if (!config.value) return
  errorMessage.value = null
  saving.value = true
  try {
    config.value = await configApi.put(config.value)
    savedAt.value = new Date().toLocaleTimeString()
  } catch (err) {
    errorMessage.value = err instanceof ApiError ? err.message : String(err)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div v-if="config" class="config">
    <h2>Config</h2>

    <section class="section">
      <h3>LLM</h3>
      <label class="field">
        <span>Provider</span>
        <input :value="field('app', 'llm_provider')" @change="(e) => setField('app', 'llm_provider', (e.target as HTMLInputElement).value)" />
      </label>
      <label class="field">
        <span>API Key</span>
        <input
          type="password"
          :value="field('app', `${field('app', 'llm_provider')}_api_key`)"
          @change="(e) => setField('app', `${field('app', 'llm_provider')}_api_key`, (e.target as HTMLInputElement).value)"
        />
      </label>
    </section>

    <section class="section">
      <h3>Stock providers</h3>
      <label class="field">
        <span>Pexels API Key</span>
        <input
          type="password"
          :value="field('app', 'pexels_api_keys')"
          @change="(e) => setField('app', 'pexels_api_keys', (e.target as HTMLInputElement).value)"
        />
      </label>
      <label class="field">
        <span>Pixabay API Key</span>
        <input
          type="password"
          :value="field('app', 'pixabay_api_keys')"
          @change="(e) => setField('app', 'pixabay_api_keys', (e.target as HTMLInputElement).value)"
        />
      </label>
    </section>

    <section class="section">
      <h3>UI</h3>
      <label class="checkbox">
        <input
          type="checkbox"
          :checked="config.ui.hide_log === true"
          @change="(e) => setField('ui', 'hide_log', String((e.target as HTMLInputElement).checked))"
        />
        <span>Ocultar log</span>
      </label>
    </section>

    <button :disabled="saving" @click="save">{{ saving ? 'Salvando…' : 'Salvar' }}</button>
    <p v-if="savedAt" class="saved">Salvo às {{ savedAt }}</p>
    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </div>
</template>

<style scoped>
.config {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  max-width: 28rem;
}

.section {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

h3 {
  margin: 0;
  font-size: 0.9rem;
  color: var(--cockpit-text-muted);
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.85rem;
}

.field input {
  padding: 0.5rem 0.6rem;
  border-radius: 0.4rem;
  border: 1px solid var(--cockpit-border);
  background: var(--cockpit-bg);
  color: var(--cockpit-text);
}

.checkbox {
  display: flex;
  align-items: center;
  gap: 0.5rem;
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
}

.saved {
  color: var(--cockpit-success);
  font-size: 0.8rem;
}

.error {
  color: var(--cockpit-danger);
  font-size: 0.85rem;
}
</style>
