/// <reference types="vite/client" />

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

import { loadEnv } from 'vite';

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
    // Pre-bundle heavy deps at server START (not lazily on the first client
    // request), so the first page load isn't blocked by on-demand dep
    // optimization + re-parse of lucide/framer/three on the critical path.
    optimizeDeps: {
      // web-llm and transformers.js ship their own workers/WASM/ONNX
      // runtimes — esbuild pre-bundling corrupts them into an unfetchable
      // .vite/deps chunk ("Failed to fetch dynamically imported module").
      // Excluding forces native ESM serving, which is what both libs expect.
      exclude: ['@mlc-ai/web-llm', '@huggingface/transformers'],
      include: [
        'react', 'react-dom', 'react/jsx-runtime',
        'framer-motion', 'lucide-react',
        'three', '@react-three/fiber', '@react-three/drei',
        'react-markdown', 'swr', 'clsx', 'tailwind-merge',
      ],
    },
    build: {
      target: 'es2020',
      cssCodeSplit: true,
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
      port: 3000,
      host: '0.0.0.0',
      allowedHosts: true,
      // COEP: `credentialless` (Chrome 96+) keeps WebLLM/SharedArrayBuffer
      // threading protected (COOP same-origin + COEP) WHILE allowing
      // cross-origin, no-CORP third-party scripts — e.g. the Telegram WebApp
      // SDK in index.html — to load. `require-corp` blocks them with
      // ERR_BLOCKED_BY_RESPONSE...Coep, so window.Telegram === undefined.
      headers: {
        'Cross-Origin-Opener-Policy': 'same-origin',
        'Cross-Origin-Embedder-Policy': 'credentialless',
      },
      // Warm-transform the entry + initially-rendered heavy modules at server
      // start so first-load time isn't consumed by on-demand transforms.
      warmup: {
        clientFiles: [
          './src/main.tsx',
          './src/App.tsx',
          './src/components/sidebar/Sidebar.tsx',
          './src/components/sidebar/AgentStatus.tsx',
          './src/components/RaceCard.tsx',
          './src/components/layout/Header.tsx',
          './src/components/layout/Footer.tsx',
          './src/store/hud-store.ts',
          './src/engine/data-bridge.ts',
          './src/hooks/useHUD.ts',
          './src/lib/api-fetch.ts',
        ],
      },
      proxy: {
        '/ollama': {
          target: 'http://127.0.0.1:11434',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/ollama/, ''),
          secure: false,
        },
        '/api/health': { target: 'https://striketips-mcp.gmphorg379.workers.dev', changeOrigin: true, secure: true },
        '/api/edge': { target: 'https://striketips-mcp.gmphorg379.workers.dev', changeOrigin: true, secure: true },
        '/api/kelly': { target: 'https://striketips-mcp.gmphorg379.workers.dev', changeOrigin: true, secure: true },
        '/api/circuit': { target: 'https://striketips-mcp.gmphorg379.workers.dev', changeOrigin: true, secure: true },
        '/api/bayesian': { target: 'https://striketips-mcp.gmphorg379.workers.dev', changeOrigin: true, secure: true },
        '/api/keywords': { target: 'https://striketips-mcp.gmphorg379.workers.dev', changeOrigin: true, secure: true },
        '/api/evaluate': { target: 'https://striketips-mcp.gmphorg379.workers.dev', changeOrigin: true, secure: true },
        '/api/verify-card': { target: 'https://striketips-mcp.gmphorg379.workers.dev', changeOrigin: true, secure: true },
        '/api/patch-html': { target: 'https://striketips-mcp.gmphorg379.workers.dev', changeOrigin: true, secure: true },
        '/api/racing/form': { target: 'https://striketips-mcp.gmphorg379.workers.dev', changeOrigin: true, secure: true },
        '/api/racing/odds': { target: 'https://striketips-mcp.gmphorg379.workers.dev', changeOrigin: true, secure: true },
        '/api/knowledge': { target: 'https://striketips-mcp.gmphorg379.workers.dev', changeOrigin: true, secure: true },
        '/mcp': {
          target: 'https://striketips-mcp.gmphorg379.workers.dev',
          changeOrigin: true,
          secure: true,
          ws: true,
          headers: apiKeyHeader,
        },
        '/api': {
          target: 'https://gmpho--strike-tips-racing-serve-api.modal.run',
          changeOrigin: true,
          secure: true,
          headers: apiKeyHeader,
        },
        '/docs': {
          target: 'https://gmpho--strike-tips-racing-serve-api.modal.run',
          changeOrigin: true,
          secure: true,
          headers: apiKeyHeader,
        },
        '/openapi.json': {
          target: 'https://gmpho--strike-tips-racing-serve-api.modal.run',
          changeOrigin: true,
          secure: true,
          headers: apiKeyHeader,
        },
        '/v1': {
          target: 'https://gmpho--strike-tips-racing-serve-api.modal.run',
          changeOrigin: true,
          secure: true,
          headers: apiKeyHeader,
        }
      }
    }
  };
});
