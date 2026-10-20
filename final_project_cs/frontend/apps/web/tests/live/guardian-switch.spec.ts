import { expect, test, type Page } from "@playwright/test";
import { fillPlanAsk, mockServer, openRegistration, start, TRIP_ID, tripScreen, weekAhead } from "./helpers";

/**
 * `[2026-10-19 사용자 결정 — ST4F-613]` 관리 콘솔의 항로 지킴이 스위치를 끄면(공개 읽기 `GET /v1/web/features` → `{guardian: false}`) 웹에서 항로 지킴이를 숨긴다 —
 * 계획 담기의 카드 · 등록 전 화면의 머리 아이콘 · 등록한 여행의 메뉴 서랍 아이콘이 없고, 설문에 `on_disruption` 을 싣지 않는다(여유는 그대로 간다).
 * 계약: `wiki/external/rest-endpoints/web-trips.md` 「항로 지킴이 운영 스위치」.
 * 테스트용 mock 서버로 도는 자동 시험이다(화면 반응을 본다 — 실서버 확인 아님).
 */
const PLAN = "10/1 09:00 경복궁 관람";
const send = (page: Page) => page.getByRole("button", { name: "계획 확인하기" });
const keeper = (page: Page) => page.getByRole("button", { name: /항로 지킴이 (끄기|켜기)/ });
const card = (page: Page) => page.getByRole("dialog", { name: /항로 지킴이/ });
async function menu(page: Page) {
  if (await page.getByRole("button", { name: "메뉴 닫기" }).count() === 0) await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await expect(page.getByRole("button", { name: "메뉴 닫기" })).toBeVisible();
}

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

test("끄면 「계획 확인하기」가 카드 없이 곧장 보내고, 읽는 중 · 계획 확인 화면에 머리 아이콘이 없으며, 확정에는 on_disruption 없이 여유만 간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ features: "guardian_off" });
  await start(page);
  await openRegistration(page);
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await send(page).click();
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);
  await expect(card(page)).toHaveCount(0);
  await expect(keeper(page)).toHaveCount(0);
  expect(await server.received("POST", "/v1/web/trip-intakes")).toHaveLength(1);
  await page.getByRole("button", { name: "여행 등록" }).click();
  await expect(page).toHaveURL(/\/trips\/[0-9a-f-]+$/);
  const [confirm] = await server.received("POST", "/confirm");
  expect(confirm.body).toMatchObject({ survey: { version: "2026-09-24.v1", pace: "moderate" } });
  expect((confirm.body as { survey: Record<string, unknown> }).survey).not.toHaveProperty("on_disruption");
  // 세션 없이 읽는 공개 읽기 — 한 번이면 된다
  expect((await server.received("GET", "/v1/web/features")).length).toBeGreaterThanOrEqual(1);
});

test("한 번 켠 기억이 이 브라우저에 있어도 끈 동안은 묻지도 싣지도 않는다 — 「계획 짜 주기」에도 여유만 간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ features: "guardian_off", readingPolls: 0 });
  await page.addInitScript(() => localStorage.setItem("triPilot.guardianDefault.v1", "on"));
  await start(page);
  await openRegistration(page);
  await fillPlanAsk(page, { start: weekAhead(), days: 2, party: 2 });
  await send(page).click();
  await expect(page).toHaveURL(/\/trips\/[0-9a-f-]+$/, { timeout: 15_000 });
  await expect(card(page)).toHaveCount(0);
  const [plan] = await server.received("POST", "/plan");
  expect(plan.body).toMatchObject({ survey: { version: "2026-09-24.v1", pace: "moderate" } });
  expect((plan.body as { survey: Record<string, unknown> }).survey).not.toHaveProperty("on_disruption");
});

for (const features of ["off", "on"] as const) {
  test(`공개 읽기가 ${features === "off" ? "없는 옛 서버(404)" : "켜짐"}이면 지금처럼 카드가 묻는다`, async ({ page, request }) => {
    const server = mockServer(request);
    await server.scenario({ features });
    await start(page);
    await openRegistration(page);
    await page.getByLabel("나의 여행 계획").fill(PLAN);
    await send(page).click();
    await expect(card(page)).toBeVisible();
    // `[2026-10-20 ST4F-615]` 「직접 입력」은 서버가 받은 뒤(빠른 거름 통과)에 카드가 묻는다 — 접수 한 번
    expect(await server.received("POST", "/v1/web/trip-intakes")).toHaveLength(1);
  });
}

test("등록한 여행: 끈 동안은 여행 조회에 guardian 이 없어 메뉴 서랍에 아이콘이 없고, 알림 링크 ?guardian=on 도 카드를 열지 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ guardian: "on", features: "guardian_off" });
  await start(page);
  await page.goto(`/trips/${TRIP_ID}?guardian=on`);
  await expect(tripScreen(page)).toBeVisible();
  await page.waitForTimeout(500);
  await expect(card(page)).toHaveCount(0);
  await menu(page);
  await expect(keeper(page)).toHaveCount(0);
  expect(await server.received("POST", "/guardian")).toHaveLength(0);
});

test("여행 화면을 연 사이 운영자가 끄면 누른 것이 409 로 거절되고, 아이콘을 거두며 「지금은 항로 지킴이를 쓸 수 없어요.」라고 말한다(다시 시도하기 없음)", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ guardian: "on", features: "on" });
  await start(page);
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(tripScreen(page)).toBeVisible();
  await menu(page);
  await expect(page.getByRole("button", { name: "항로 지킴이 끄기" })).toBeVisible();
  await server.scenario({ features: "guardian_off" });
  await page.getByRole("button", { name: "항로 지킴이 끄기" }).click();
  const line = page.getByRole("status").filter({ hasText: "지금은 항로 지킴이를 쓸 수 없어요." });
  await expect(line).toBeVisible();
  await expect(line.getByRole("button", { name: "다시 시도하기" })).toHaveCount(0);
  await expect(keeper(page)).toHaveCount(0);
  expect((await server.received("POST", "/guardian")).map((entry) => entry.body)).toEqual([{ enabled: false, via: "header" }]);
});
