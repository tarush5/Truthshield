import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    // Fail the build on a chunk large enough to hurt first paint, rather than
    // printing a warning nobody reads.
    chunkSizeWarningLimit: 300,
    rollupOptions: {
      output: {
        // React is the only vendor bundle worth splitting now: it changes far
        // less often than app code, so it stays cached across deploys.
        manualChunks: { react: ['react', 'react-dom', 'react-router-dom'] },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Dev-only convenience so the app can be opened on localhost:5173 and
      // still reach the API without a CORS round trip.
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
});
