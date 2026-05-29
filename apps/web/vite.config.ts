import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Avoid Ship/Vite defaults (5173) and common API ports (3000, 8787)
    port: 5184,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:5183',
        changeOrigin: true,
      },
    },
  },
});
