import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

export default defineConfig({
  plugins: [react()],
  test: {
    // Use jsdom for DOM simulation
    environment: 'jsdom',
    
    // Global test setup
    setupFiles: ['./src/tests/setup.js'],
    
    // Coverage configuration
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
    
    // Test execution settings
    globals: true,
    restoreMocks: true,
    clearMocks: true,
    
    // Parallel execution
    pool: 'forks',
    
    // Timeout settings
    testTimeout: 10000,
    hookTimeout: 10000
  },
  
  // Resolve aliases (match vite config)
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
      '@components': resolve(__dirname, './src/components'),
      '@pages': resolve(__dirname, './src/pages'),
      '@hooks': resolve(__dirname, './src/hooks'),
      '@store': resolve(__dirname, './src/store'),
      '@api': resolve(__dirname, './src/api'),
      '@utils': resolve(__dirname, './src/utils')
    }
  }
})
