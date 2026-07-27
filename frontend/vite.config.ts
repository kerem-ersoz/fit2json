import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// FitSift dev/build config.
// - `base` is env-configurable so the app can later be served under a path
//   (e.g. /fitsift) without code changes; defaults to "/".
// - dev server proxies /api to the FastAPI backend and binds all interfaces
//   (host: true) so the UI is reachable from a phone on the same network.
export default defineConfig(() => ({
  base: process.env.VITE_BASE_PATH || '/',
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': { target: process.env.VITE_API_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
}))
