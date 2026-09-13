import { defineConfig } from 'vitest/config';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const packageDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  resolve: {
    alias: {
      '@composio/json-schema-to-zod': path.resolve(
        packageDir,
        '../json-schema-to-zod/src/index.ts'
      ),
    },
  },
  test: {
    exclude: ['**/node_modules/**', '**/dist/**'],
  },
});
