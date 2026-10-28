import { fileURLToPath } from 'node:url';
import { defineConfig } from '@playwright/test';

const root = fileURLToPath(new URL('../../', import.meta.url));
const python = process.env.SIGNALDESK_PYTHON || 'python3';
export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  use: {
    baseURL: 'http://127.0.0.1:8787',
    headless: true,
    viewport: { width: 1440, height: 1000 },
    launchOptions: process.env.SIGNALDESK_BROWSER
      ? { executablePath: process.env.SIGNALDESK_BROWSER }
      : {},
    screenshot: 'only-on-failure',
  },
  reporter: [['list']],
  webServer: {
    cwd: root,
    command: `${python} tools/web/tests/seed_workspace.py --data-dir .tmp/browser-workspace && ${python} launch.py --port 8787 --data-dir .tmp/browser-workspace --no-refresh`,
    url: 'http://127.0.0.1:8787/api/health',
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
