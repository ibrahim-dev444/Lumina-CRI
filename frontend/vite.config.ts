import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // The browser only talks to localhost:5173. Vite forwards /api calls to Django on 8000,
    // so login cookies work without any cross-site setup.
    proxy: {
      // 127.0.0.1, not localhost: Node may resolve localhost to IPv6 (::1), but runserver listens on IPv4.
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
