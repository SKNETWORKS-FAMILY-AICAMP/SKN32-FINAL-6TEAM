import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests against the REAL server (`NEXT_PUBLIC_API_BASE`, the web app on :3100 in live mode). Run with
 * `REAL_SERVER_E2E=1 npm run test:real`, with the web app (`npm run dev`) and the server both up.
 *
 * ★These have real side effects: every registration sends a notice to the team's chat channel, spends place-lookup and
 *   model calls, and leaves a test customer and trip in the database. That is why they only run when asked for.
 */
if (!process.env.REAL_SERVER_E2E) {
  throw new Error("These tests register real trips on the real server (a notice goes to the team's chat channel). Set REAL_SERVER_E2E=1 to run them.");
}

export default defineConfig({
  testDir: "./tests/real",
  testMatch: /.*\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  timeout: 300_000,
  expect: { timeout: 20_000 },
  reporter: "list",
  use: {
    ...devices["Desktop Chrome"],
    channel: process.env.PLAYWRIGHT_CHANNEL || "chromium",
    baseURL: process.env.REAL_WEB_URL || "http://127.0.0.1:3100",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});
