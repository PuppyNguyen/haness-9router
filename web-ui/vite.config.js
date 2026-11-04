import { defineConfig } from 'vite';
import preact from '@preact/preset-vite';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [preact()],
  root: fileURLToPath(new URL('.', import.meta.url)),
  base: '/',
  build: {
    outDir: fileURLToPath(new URL('../agent_harness/web/dist', import.meta.url)),
    emptyOutDir: true,
    assetsDir: 'assets',
    sourcemap: false,
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test-setup.js',
    include: ['src/**/*.test.jsx'],
  },
});
