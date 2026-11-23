import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: process.env.DEPLOYCORE_DEV_API
      ? { '/api': process.env.DEPLOYCORE_DEV_API }
      : undefined,
  },
})
