import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Local development uses Vite on 5173 and proxies API requests to FastAPI on 8000.
// Docker serves the built frontend via Nginx on host port 8000.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: process.env.VITE_DEV_API_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {
        target: process.env.VITE_DEV_API_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
