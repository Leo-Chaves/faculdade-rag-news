import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
  ],
  server: {
    port: 5173,
    proxy: {
      '/auth/config': 'http://127.0.0.1:8000',
      '/news': 'http://127.0.0.1:8000',
      '/chat': 'http://127.0.0.1:8000',
      '/ingest': 'http://127.0.0.1:8000',
    },
  },
})
