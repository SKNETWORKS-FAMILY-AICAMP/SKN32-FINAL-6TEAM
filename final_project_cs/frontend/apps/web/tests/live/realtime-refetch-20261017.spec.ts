import { expect, test, type Page } from "@playwright/test";
import { mockServer, start, TRIP_ID, tripScreen } from "./helpers";

/**
 * `[2026-10-17 사용자 지적 — ST4F-603]` 서버가 바꾼 것이 새로고침해야 보이던 곳 — 프론트만으로 늦음을 줄인다. mock 서버 시험이다(화면이 언제 다시 읽는지만 본다 — 실서버 아님).
 *   - 서비스 공지 · 점검 배너: 15초마다 읽고, 탭으로 돌아오면 바로 읽는다(옛: 60초).
 *   - 문의함 목록 · 상세 · 여행 목록: 탭으로 돌아오면 다시 읽는다. 연 문의는 30초마다.
 *   - 여행 화면 초인종의 알림 신호: 알림 목록과 함께 일정 본문(재난 정지 칩) · 해제 브리핑도 다시 읽는다.
 *   - 초인종 연결이 상한(429)에 걸리면 30초 읽기로 내려간다.
 * ★시간은 가짜 시계로 건너뛴다(`page.clock`) — 화면의 폴링 타이머를 건너뛴 뒤 다시 그려질 틈만 실제로 기다린다.
 */
test.beforeEach(async ({ page, request }) => {
  await mockServer(request).reset();
  await start(page);
});

/** The tab goes to the background and comes back (React Query re-reads on `visibilitychange`). */
async function tabComesBack(page: Page) {
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "hidden" });
    document.dispatchEvent(new Event("visibilitychange", { bubbles: true }));       // 실제 브라우저처럼 창(window)까지 올라간다 — React Query 는 창에서 듣는다
    Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "visible" });
    document.dispatchEvent(new Event("visibilitychange", { bubbles: true }));
  });
}

const banner = (page: Page) => page.getByRole("complementary", { name: "서비스 공지" });

test("운영자가 공지를 올리면 새로고침 없이 15초 안에 배너가 뜬다 — 예전 60초가 아니다", async ({ page, request }) => {
  const server = mockServer(request);
  await page.clock.install();
  await page.goto("/trips");
  await expect(page.getByRole("heading", { name: "내 여행", level: 1 })).toBeVisible();
  await expect(banner(page)).toHaveCount(0);
  await server.scenario({ serviceNotice: "one" });
  await page.clock.fastForward(16_000);
  await expect(banner(page)).toContainText("서비스 점검 예정 안내");
  const box = (await banner(page).boundingBox())!;
  expect(box.y).toBeLessThan(40);                                                      // `[2026-10-17 사용자 지시]` 화면 맨 위에 뜬다(옛: 아래)
});

test("탭으로 돌아오면 공지를 바로 다시 읽는다", async ({ page, request }) => {
  const server = mockServer(request);
  await page.goto("/trips");
  await expect(page.getByRole("heading", { name: "내 여행", level: 1 })).toBeVisible();
  await expect(banner(page)).toHaveCount(0);
  await server.scenario({ serviceNotice: "one" });
  await tabComesBack(page);
  await expect(banner(page)).toContainText("서비스 점검 예정 안내", { timeout: 5_000 });
});

test("문의함과 여행 목록은 탭으로 돌아오면 다시 읽고, 연 문의는 30초마다 다시 읽는다", async ({ page, request }) => {
  const server = mockServer(request);
  const count = async (suffix: string) => (await server.received("GET", suffix)).length;
  await page.goto("/trips");
  await expect(page.getByRole("heading", { name: "내 여행", level: 1 })).toBeVisible();
  await expect.poll(() => count("/v1/web/trips")).toBeGreaterThan(0);
  const tripsBefore = await count("/v1/web/trips");
  await tabComesBack(page);
  await expect.poll(() => count("/v1/web/trips")).toBeGreaterThan(tripsBefore);

  await page.goto("/support");
  await expect.poll(() => count("/v1/web/support/inquiries")).toBeGreaterThan(0);
  const listBefore = await count("/v1/web/support/inquiries");
  await tabComesBack(page);
  await expect.poll(() => count("/v1/web/support/inquiries")).toBeGreaterThan(listBefore);
});

test("연 문의는 답변을 기다리는 동안 30초마다 다시 읽는다", async ({ page, request }) => {
  const server = mockServer(request);
  const count = async () => (await server.received("GET", "/v1/web/support/inquiries")).length;
  await page.clock.install();
  await page.goto("/support/inquiry-1");
  await expect.poll(count).toBeGreaterThan(0);
  const before = await count();
  await page.clock.fastForward(31_000);
  await expect.poll(count).toBeGreaterThan(before);
});

// 해제 브리핑(`…/safety/recovery`)은 그 조각이 화면에 있을 때만 읽는다 — 이 장면(정지 없음)에서는 처음부터 읽지 않아 다시 읽기를 셀 수 없다. 알림 신호가 그것도 무효로 만드는 것은 코드(`use-trip-events.ts`)로만 본다.
test("초인종의 알림 신호가 오면 알림과 함께 일정 본문(재난 정지 칩)도 다시 읽는다", async ({ page, request }) => {
  const server = mockServer(request);
  const count = async (suffix: string) => (await server.received("GET", suffix)).length;
  await server.scenario({ bell: "on" });
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(tripScreen(page)).toBeVisible();
  await expect(page.locator("#trip-bell")).toHaveAccessibleName(/알림 센터 열기/);     // 화면이 다 그려진 뒤(알림을 읽은 뒤)를 기준으로 센다
  await page.waitForTimeout(500);
  const trip = await count(`/v1/web/trips/${TRIP_ID}`);
  await expect.poll(() => server.ring(["notice"])).toBeGreaterThan(0);
  await expect.poll(() => count(`/v1/web/trips/${TRIP_ID}`)).toBeGreaterThan(trip);
});

test("초인종 연결이 상한(429)에 걸리면 알림을 30초마다 다시 읽는다 — 옛 화면은 다시 잇기만 하고 읽지 않았다", async ({ page, request }) => {
  const server = mockServer(request);
  const count = async () => (await server.received("GET", `/v1/web/trips/${TRIP_ID}/notices`)).length;
  await server.scenario({ bell: "busy" });
  await page.clock.install();
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(tripScreen(page)).toBeVisible();
  await expect.poll(async () => (await server.received("GET", `/v1/web/trips/${TRIP_ID}/events`)).length).toBeGreaterThan(0);
  const before = await count();
  await page.clock.fastForward(31_000);
  await expect.poll(count).toBeGreaterThan(before);
});
