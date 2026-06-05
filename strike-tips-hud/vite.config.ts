/// <reference types="vite/client" />

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Load env for dev proxy headers — Vite's envDir picks up ../.env at build time,
// but for proxy config we need process.env at dev server start.
import { loadEnv } from 'vite';

function getApiKeyHeader(): Record<string, string> {
  // Use VITE_STRIKE_TIPS_API_KEY if set (for convenience), else STRIKE_TIPS_API_KEY
  const key = process.env.STRIKE_TIPS_API_KEY || process.env.VITE_STRIKE_TIPS_API_KEY || '';
  if (!key) return {};
  return { 'X-API-KEY': key };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd() + '/..', '');
  const key = env.STRIKE_TIPS_API_KEY || process.env.STRIKE_TIPS_API_KEY || '';
  const apiKeyHeader = key ? { 'X-API-KEY': key } : {};

  return {
    envDir: '..',
    plugins: [
      react(),
      tailwindcss()
    ],
    resolve: {
      tsconfigPaths: true
    },
    build: {
      target: 'es2015',
      rollupOptions: {
        output: {
          manualChunks(id: string) {
            if (id.includes('node_modules/react-dom') || id.includes('node_modules/react/')) return 'vendor-react'
            if (id.includes('node_modules/framer-motion')) return 'vendor-framer'
            if (id.includes('node_modules/three') || id.includes('node_modules/@react-three')) return 'vendor-three'
            if (id.includes('node_modules/lucide-react')) return 'vendor-icons'
          },
        },
      },
    },
    server: {
      port: 5173,
      proxy: {
        '/ollama': {
          target: 'http://127.0.0.1:11434',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/ollama/, ''),
          secure: false,
        },
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
          secure: false,
          headers: apiKeyHeader,
        },
        '/mcp': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
          ws: true,
          headers: apiKeyHeader,
        },
        '/docs': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
          headers: apiKeyHeader,
        },
        '/openapi.json': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
          headers: apiKeyHeader,
        }
      }
    }
  };
});
