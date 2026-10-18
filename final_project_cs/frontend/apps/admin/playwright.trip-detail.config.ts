import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir: './tests/live', testMatch: /trip-detail.*\.spec\.ts/, outputDir: `./test-results/trip-detail-${Date.now()}`, workers: 1,
  timeout: 45000, expect: { timeout: 10000 }, reporter: 'list',
  use: { ...devices['Desktop Chrome'], channel: 'chrome', baseURL: 'http://127.0.0.1:3384' },
  webServer: { command: process.env.TRIP_DETAIL_PRODUCTION ? 'node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3384' : 'node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3384', url: 'http://127.0.0.1:3384', reuseExistingServer: false, timeout: 120000, env: { NEXT_PUBLIC_ADMIN_DATA_MODE: 'live', NEXT_TELEMETRY_DISABLED: '1', ADMIN_OPS_API_URL: 'http://127.0.0.1:3385', ...(process.env.TRIP_DETAIL_PRODUCTION ? { NEXT_DIST_DIR: process.env.NEXT_DIST_DIR || '.next-trip-production' } : {}) } },
});
