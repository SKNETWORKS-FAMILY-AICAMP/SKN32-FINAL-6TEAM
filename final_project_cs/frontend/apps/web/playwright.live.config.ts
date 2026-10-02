import { defineConfig, devices } from "@playwright/test";

/**
 * 테스트용 모방 서버로 도는 화면 자동 시험 — ★실제 서버가 아니다. 실제 화면을 실제 브라우저로 열되, 서버 자리에는
 * 서버의 웹 API 모양만 흉내 내는 테스트용 모방 서버(`tests/live/stub-server.mjs`)를 둔다. Run with `npm run test:live`.
 * 실제 서버 확인은 `tests/real/`(`npm run test:real`)이 한다. 이 시험 통과를 「실제로 된다」로 보고하지 않는다.
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
