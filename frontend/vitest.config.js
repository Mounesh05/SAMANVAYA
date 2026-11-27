import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/tests/setup.js'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'json'],
      reportsDirectory: '../coverage/frontend',
      include: ['src/**/*.{js,jsx}'],
      exclude: [
        'src/main.jsx',
        'src/**/*.test.{js,jsx}',
        'src/**/*.spec.{js,jsx}',
        'src/tests/**'
      ],
      thresholds: {
        lines: 70,
        branches: 70,
        functions: 70,
        statements: 70
      }
    },
    globals: true,
    restoreMocks: true,
    clearMocks: true,
    pool: 'forks',
    testTimeout: 10000,
    hookTimeout: 10000
  }
})
