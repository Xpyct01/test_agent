import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The dev server proxies the API, so the browser talks to one origin.
const apiUrl = process.env.TRIP_API_URL ?? 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/agui': { target: apiUrl, changeOrigin: true },
      '/health': { target: apiUrl, changeOrigin: true },
    },
  },
});
