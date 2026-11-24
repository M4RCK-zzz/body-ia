import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    host: 'localhost',
    port: 5173,
    strictPort: true,
  },
  build: {
    // El visor 3D (three.js + drei) se carga en su propio chunk por ruta lazy
    // (`LazyViewer`), así el resto de la app no descarga WebGL. Ese chunk pesa
    // ~1 MB minificado: se sube el límite de aviso para no ensuciar el build.
    chunkSizeWarningLimit: 1100,
  },
})
