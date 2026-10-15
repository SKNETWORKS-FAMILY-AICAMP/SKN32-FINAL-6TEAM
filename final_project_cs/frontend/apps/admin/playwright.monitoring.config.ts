import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir:'./tests/live',testMatch:'monitoring.spec.ts',workers:1,
  outputDir:'./test-results/monitoring',reporter:'list',timeout:45000,
  use:{...devices['Desktop Chrome'],channel:process.env.PLAYWRIGHT_CHANNEL||'msedge',baseURL:'http://127.0.0.1:3368'},
  webServer:{command:'node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3368',url:'http://127.0.0.1:3368',reuseExistingServer:false,timeout:120000,
    env:{NEXT_DIST_DIR:'.next-watch-monitoring-1009',NEXT_PUBLIC_ADMIN_DATA_MODE:'live'}},
});
