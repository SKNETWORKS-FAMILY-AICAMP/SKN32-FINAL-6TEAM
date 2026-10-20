import { expect, test } from "@playwright/test";
import { checkPlan, mockServer, start } from "./helpers";

const PLAN = "10/1 09:00 경복궁 관람\n12:00 광장시장 점심";
const screen = '[data-replay]';
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

test("「직접 입력」은 입력 화면에서 보내고(ST4F-615 — 진행 화면은 서버가 받은 뒤), 첫 조회를 기다리는 동안에도 SSE는 먼저 연결된다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ intakeDelay: 1200, readingPolls: 3, intakeEvents: "on", review: "on", board: "rich" });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  let screenBeforeSending: boolean | null = null;
  let sendingFromEntry = false;
  await page.route("**/v1/web/trip-intakes", async (route) => {
    if (route.request().method() === "POST") {
      screenBeforeSending = await page.locator(screen).isVisible();
      sendingFromEntry = await page.getByLabel("나의 여행 계획").isDisabled();
      if (process.env.LOADING_SHOTS) await page.screenshot({ path: `${process.env.LOADING_SHOTS}/01-before-send.png`, fullPage: true });
    }
    await route.continue();
  });
  await page.route(/\/v1\/web\/trip-intakes\/[0-9a-f-]{36}$/, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 2500));
    await route.continue();
  });
  await checkPlan(page);
  await expect(page.locator(screen)).toBeVisible();
  // `[2026-10-20 ST4F-615]` 보낼 때는 아직 입력 화면이다(입력칸이 잠긴 채) — 진행 화면은 서버가 받은 뒤에 나온다
  await expect.poll(() => screenBeforeSending).toBe(false);
  expect(sendingFromEntry).toBe(true);
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]{36}$/);
  await expect.poll(async () => (await server.received("GET", "/events")).length).toBeGreaterThan(0);
  await expect(page.locator(screen)).toBeVisible();
  await expect(page.getByText("여행 정보를 불러오고 있어요.")).toHaveCount(0);
  expect(await server.received("POST", "/v1/web/trip-intakes")).toHaveLength(1);
});

test("설문에 머무는 동안 재생이 소진되지 않고 다음을 누른 순간부터 축적된 결과를 재생한다", async ({ page, request }) => {
  const server = mockServer(request);
  // `[2026-10-20 C안]` 확인이 필요한 일정이 있으면 첫 검사가 그 카드에서 멈춰 묻는다 — 재생 · 지도를 보는 이 시험은 고칠 것이 없는 판(`calm`)으로 끝까지 본다.
  await server.scenario({ questions: "two", readingPolls: 999, intakeEvents: "on", review: "off", board: "calm" });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await checkPlan(page);
  const pager = page.getByRole("region", { name: "질문 2개" });
  await expect(pager).toBeVisible();
  await pager.getByRole("button", { name: "택시", exact: true }).click();
  await expect(pager).toContainText("2 / 2");
  await server.scenario({ readingPolls: 0, review: "on" });
  const next = page.getByRole("button", { name: "읽어 온 계획 확인하기" });
  await expect(next).toBeEnabled();
  await expect(page.locator(screen)).toHaveAttribute("data-replay", "paused");
  const stage = await page.locator(screen).getAttribute("data-stage");
  await page.clock.install();
  await page.clock.runFor(16_000);
  await expect(page.locator(screen)).toHaveAttribute("data-stage", stage!);
  await expect(page.getByRole("article", { name: "경복궁 관람", exact: true })).toHaveCount(0);
  if (process.env.LOADING_SHOTS) {
    await page.screenshot({ path: `${process.env.LOADING_SHOTS}/02-survey-paused-desktop.png`, fullPage: true });
    await page.setViewportSize({ width: 375, height: 812 });
    await page.screenshot({ path: `${process.env.LOADING_SHOTS}/02-survey-paused-mobile.png`, fullPage: true });
  }
  await next.click();
  await expect(page.locator(screen)).toHaveAttribute("data-replay", "playing");
  await expect(page.locator(screen)).not.toHaveAttribute("data-stage", "done");
  if (process.env.LOADING_SHOTS) {
    await page.clock.runFor(5_000);
    await page.screenshot({ path: `${process.env.LOADING_SHOTS}/03-check-replaying.png`, fullPage: true });
  }
  // `[2026-10-20 C안 · 5초 자동 등록]` 결과 화면에 닿으면 5초 막대가 켜진다 — 시계를 한 번에 끝까지 돌리면 스스로 등록해 이 화면을 떠나므로 결과 화면에 닿을 때까지만 돌린다.
  for (let waited = 0; waited < 24_000 && await page.locator(screen).getAttribute("data-stage") !== "done"; waited += 1_000) await page.clock.runFor(1_000);
  await expect(page.locator(screen)).toHaveAttribute("data-stage", "done");
  await expect(page.getByRole("article", { name: "경복궁 관람", exact: true })).toBeVisible();
});

test("다음 로딩에서는 저장한 설문 답을 유지하고 첫 미응답 질문부터 이어서 보여준다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ questions: "two", readingPolls: 999, intakeEvents: "on" });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await checkPlan(page);
  const pager = page.getByRole("region", { name: "질문 2개" });
  await pager.getByRole("button", { name: "택시", exact: true }).click();
  await expect(pager).toContainText("2 / 2");
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await checkPlan(page);
  await expect(pager).toContainText("2 / 2");
  await pager.getByRole("button", { name: "이전 질문 보기" }).click();
  await expect(pager.getByRole("button", { name: "택시", exact: true })).toHaveAttribute("aria-pressed", "true");
});
