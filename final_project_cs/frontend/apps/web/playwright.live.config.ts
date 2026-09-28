import { defineConfig, devices } from "@playwright/test";

/**
 * Live-mode end-to-end tests: the real screens in a real browser against a stand-in for the server's web API
 * (`tests/live/stub-server.mjs`). Run with `npm run test:live`.
 */
export default defineConfig({
  testDir: "./tests/live",
  testMatch: /.*\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  expect: { timeout: 12_000 },
  reporter: "list",
  use: {
    ...devices["Desktop Chrome"],
    channel: process.env.PLAYWRIGHT_CHANNEL || "chromium",
    baseURL: "http://127.0.0.1:3102",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    { command: "node tests/live/stub-server.mjs", url: "http://127.0.0.1:8043/__test/log", reuseExistingServer: !process.env.CI, timeout: 30_000 },
    { command: "node tests/live/serve.mjs", url: "http://127.0.0.1:3102", reuseExistingServer: !process.env.CI, timeout: 300_000 },
  ],
});
