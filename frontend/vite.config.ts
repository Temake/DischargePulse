import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The FastAPI backend (backend/app/main.py) runs on :8000. Proxying keeps the
// browser same-origin in development, so REST calls and the run WebSocket need
// no hard-coded host.
const BACKEND = 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
      '/ws': { target: BACKEND.replace('http', 'ws'), ws: true },
    },
  },
})
