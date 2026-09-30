/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  build: {
    chunkSizeWarningLimit: 300,
    rollupOptions: {
      output: {
        // Framework code changes far less often than app code, so it stays
        // cached across deploys. Heavy, page-specific libraries (gsap, hls.js,
        // recharts) are left to route-level code splitting.
        manualChunks: (id: string) => {
          if (/node_modules[\/](react|react-dom|react-router|react-router-dom|scheduler)[\/]/.test(id)) return 'react';
          if (/node_modules[\/](@tanstack|zustand)[\/]/.test(id)) return 'data';
          return undefined;
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
});
