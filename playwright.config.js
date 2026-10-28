import { defineConfig } from '@playwright/test';

const python = process.env.SIGNALDESK_PYTHON || 'python3';
export default defineConfig({
  testDir: './tests/browser',
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
    command: `${python} tests/browser/seed_workspace.py --data-dir .tmp/browser-workspace && ${python} server.py --port 8787 --data-dir .tmp/browser-workspace --no-refresh`,
    url: 'http://127.0.0.1:8787/api/health',
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
