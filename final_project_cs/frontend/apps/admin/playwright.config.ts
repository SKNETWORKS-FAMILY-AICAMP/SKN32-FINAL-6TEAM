import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir: './tests/e2e', outputDir: './test-results/e2e', fullyParallel: true, workers: 2, timeout: 45000,
  expect: { timeout: 12000 }, reporter: 'list',
  use: { ...devices['Desktop Chrome'], channel: process.env.PLAYWRIGHT_CHANNEL || 'chromium', baseURL: 'http://127.0.0.1:3301', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  webServer: { command: 'npm run start -- --port 3301', url: 'http://127.0.0.1:3301', reuseExistingServer: false, timeout: 120000 }
});
