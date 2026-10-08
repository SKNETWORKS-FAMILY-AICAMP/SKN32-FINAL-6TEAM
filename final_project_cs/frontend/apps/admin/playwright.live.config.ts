import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir: './tests/live', outputDir: './test-results/live', workers: 1,
  timeout: 45000, expect: { timeout: 10000 }, reporter: 'list',
  use: { ...devices['Desktop Chrome'], channel: process.env.PLAYWRIGHT_CHANNEL || 'chromium', baseURL: 'http://127.0.0.1:3302' },
  webServer: { command: 'npm run start -- --port 3302', url: 'http://127.0.0.1:3302', reuseExistingServer: false, timeout: 120000 },
});
