import { writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/** GitHub Pages runs Jekyll unless told not to, and Jekyll drops _-prefixed paths. */
function nojekyll() {
  return {
    name: 'nojekyll',
    apply: 'build',
    closeBundle() {
      writeFileSync(resolve(__dirname, 'dist', '.nojekyll'), '')
    },
  }
}

export default defineConfig({
  // Relative paths, so the site works under any /<repo>/ prefix on Pages.
  base: './',
  plugins: [react(), nojekyll()],
  // MapLibre starts its worker from a URL relative to its own module, which
  // the dev server's dependency pre-bundling would break.
  optimizeDeps: { exclude: ['maplibre-gl'] },
  server: { port: 5173, strictPort: true, open: false },
  preview: { port: 4173, strictPort: true, open: false },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1100,
    rollupOptions: {
      output: {
        // libraries change less often than the app, so they cache apart
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (/[\/](react|react-dom|scheduler)[\/]/.test(id)) return 'react'
          if (/[\/](maplibre-gl|pmtiles)[\/]/.test(id)) return 'maplibre'
          return undefined
        },
      },
    },
  },
  test: { environment: 'node', include: ['src/**/*.test.js'] },
})
