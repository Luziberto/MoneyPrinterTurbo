import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': 'http://localhost:8080',
      '/tasks': 'http://localhost:8080',
    },
  },
  build: {
    // Copied into resource/public/ by scripts/build_webui.sh -- see
    // webui-vue/README.md. Not built directly into resource/public so the
    // frontend project stays self-contained.
    outDir: 'dist',
  },
})
