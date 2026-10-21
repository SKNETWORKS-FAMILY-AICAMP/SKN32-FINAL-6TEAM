import { expect, test, type Page } from "@playwright/test";
import { checkPlan, mockServer, start, TRIP_ID } from "./helpers";

/**
 * `[2026-10-20 사용자 결정 — 계획 확인 C안 · 5초 자동 등록]` 이 화면에서 지켜본 검사가 통과해 결과 화면에 닿으면 읽는 중 화면과 같은 막대(「모두 확인했어요」 · 「5초 뒤에 여행을 등록해요.」 ·
 * 「여행 등록」 · 「자동으로 넘어가지 않기」)가 뜨고 5초 뒤에 등록한다 — 테스트용 모방 서버로 도는 자동 시험(실제 서버 아님). 모방 서버의 `board: "calm"` 은 고칠 것이 없는 판이다.
 */
const INTAKE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const bar = (page: Page) => page.locator("[data-register-bar]");

async function watched(page: Page, request: Parameters<typeof mockServer>[0], change: Record<string, unknown> = {}) {
  const server = mockServer(request);
  await server.reset();
  await server.scenario({ review: "on", board: "calm", intakeEvents: "on", readingPolls: 1, ...change });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill("10/1 09:00 경복궁 관람");
  await checkPlan(page);
  await expect(bar(page)).toBeVisible({ timeout: 40_000 });
  return server;
}

test("지켜본 검사가 통과하면 막대가 뜨고 5초 뒤 스스로 등록해 여행 화면으로 간다 — 첫 안내는 띄우지 않는다", async ({ page, request }) => {
  const server = await watched(page, request);
  await expect(bar(page)).toContainText("모두 확인했어요");
  await expect(bar(page)).toContainText("5초 뒤에 여행을 등록해요.");
  await expect(bar(page).getByRole("button", { name: "자동으로 넘어가지 않기" })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "계획 확인 화면이에요" })).toHaveCount(0);
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`), { timeout: 9_000 });
  expect(await server.received("POST", `${INTAKE}/confirm`)).toHaveLength(1);
});

test("막대의 「여행 등록」은 기다리지 않고 바로 등록한다", async ({ page, request }) => {
  const server = await watched(page, request);
  await bar(page).getByRole("button", { name: "여행 등록" }).click();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`), { timeout: 4_000 });
  expect(await server.received("POST", `${INTAKE}/confirm`)).toHaveLength(1);
});

test("「자동으로 넘어가지 않기」를 누르면 막대가 닫히고 결과 화면에 그대로 남는다 — 스스로 등록하지 않는다", async ({ page, request }) => {
  const server = await watched(page, request);
  await bar(page).getByRole("button", { name: "자동으로 넘어가지 않기" }).click();
  await expect(bar(page)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "여행 등록" })).toBeVisible();          // 결과 화면의 둥근 단추
  await page.waitForTimeout(6_500);
  expect(await server.received("POST", `${INTAKE}/confirm`)).toHaveLength(0);
  await expect(page).toHaveURL(new RegExp(`/intakes/${INTAKE}$`));
});

// `[2026-10-20 사용자 결정]` 막대 밖 화면을 누르기 · 키 · 휠, 다른 탭 · 앱으로 넘어가기는 「자동으로 넘어가지 않기」와 같다.
async function stoppedByItself(page: Page, server: ReturnType<typeof mockServer>) {
  await expect(bar(page)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "여행 등록" })).toBeVisible();          // 결과 화면의 둥근 단추
  await page.waitForTimeout(6_500);
  expect(await server.received("POST", `${INTAKE}/confirm`)).toHaveLength(0);
}

test("막대 밖 화면을 누르면 막대가 닫히고 스스로 등록하지 않는다", async ({ page, request }) => {
  const server = await watched(page, request);
  await page.getByRole("article", { name: "경복궁 관람" }).getByRole("heading").getByRole("button").click();
  await stoppedByItself(page, server);
});

/** Wheels at a point a little above (`above` > 0) or inside the bar, after checking what lies there. */
async function wheelAt(page: Page, above: number, inBar: boolean) {
  const box = await bar(page).boundingBox();
  if (!box) throw new Error("no bar");
  const at = { x: box.x + box.width / 2, y: above > 0 ? box.y - above : box.y + box.height / 2 };
  expect(await page.evaluate(({ x, y }) => Boolean(document.elementFromPoint(x, y)?.closest("[data-register-bar]")), at)).toBe(inBar);
  await page.mouse.move(at.x, at.y);
  await page.mouse.wheel(0, 120);
}

test("막대 위쪽 목록에서 휠을 굴리면 막대가 닫히고 스스로 등록하지 않는다", async ({ page, request }) => {
  const server = await watched(page, request);
  await wheelAt(page, 40, false);
  await stoppedByItself(page, server);
});

test("막대 위에서 휠을 굴려도 닫힌다 — 막대가 목록 끝을 덮고 있다", async ({ page, request }) => {
  const server = await watched(page, request);
  await wheelAt(page, 0, true);
  await stoppedByItself(page, server);
});

test("막대의 단추가 아닌 곳(글자)을 눌러도 닫힌다", async ({ page, request }) => {
  const server = await watched(page, request);
  await bar(page).getByText("모두 확인했어요").click();
  await stoppedByItself(page, server);
});

test("키를 누르면 막대가 닫히고 스스로 등록하지 않는다", async ({ page, request }) => {
  const server = await watched(page, request);
  await page.keyboard.press("Tab");
  await stoppedByItself(page, server);
});

test("다른 탭으로 넘어가 화면이 가려지면 막대가 닫히고 스스로 등록하지 않는다", async ({ page, request }) => {
  const server = await watched(page, request);
  // 화면 가림은 브라우저가 내는 사건을 흉내 낸다(실제 탭 · 앱 전환은 이 시험이 하지 않는다).
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "hidden" });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await stoppedByItself(page, server);
});

test("다른 앱으로 넘어가 창이 초점을 잃으면 막대가 닫히고 스스로 등록하지 않는다", async ({ page, request }) => {
  const server = await watched(page, request);
  await page.evaluate(() => window.dispatchEvent(new Event("blur")));                 // 창 초점 잃음을 흉내 낸다
  await stoppedByItself(page, server);
});

test("결과 화면에서 고치기를 시작하면 막대가 닫히고 다시 뜨지 않는다", async ({ page, request }) => {
  const server = await watched(page, request);
  await page.getByRole("article", { name: "경복궁 관람" }).getByRole("heading").getByRole("button").click();
  await page.getByRole("button", { name: "경복궁 관람 수정" }).click();
  await expect(bar(page)).toHaveCount(0);
  await page.getByRole("button", { name: "바꾸기 그만두기" }).click();
  await page.waitForTimeout(6_500);
  await expect(bar(page)).toHaveCount(0);
  expect(await server.received("POST", `${INTAKE}/confirm`)).toHaveLength(0);
});

test("등록이 거절되면 막대가 닫히고 결과 화면이 그 말을 한다 — 다시 스스로 보내지 않는다", async ({ page, request }) => {
  const server = await watched(page, request, { fail: "confirm" });
  await bar(page).getByRole("button", { name: "여행 등록" }).click();
  await expect(bar(page)).toHaveCount(0);
  await expect(page.getByText(/요청을 처리하지 못했어요/)).toBeVisible();                              // 앱이 서버 오류(500)를 말하는 문장
  await page.waitForTimeout(6_500);
  expect(await server.received("POST", `${INTAKE}/confirm`)).toHaveLength(1);
});

test("검사가 끝난 접수를 다시 열면 막대 없이 결과 화면 — 「여행 등록」을 누를 때만 등록한다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.reset();
  await server.scenario({ review: "on", board: "calm", readingPolls: 0 });
  await start(page);
  await page.goto(`/intakes/${INTAKE}`);
  await expect(page.locator('main[data-stage="done"]')).toBeVisible({ timeout: 15_000 });
  await page.waitForTimeout(6_500);
  await expect(bar(page)).toHaveCount(0);
  expect(await server.received("POST", `${INTAKE}/confirm`)).toHaveLength(0);
});

test("멈추고 고르기로 다 고친 뒤 결과 화면에 닿아도 막대가 뜬다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.reset();
  await server.scenario({ review: "on", board: "rich", intakeEvents: "on", readingPolls: 1, moveOptions: "on" });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill("10/1 09:00 경복궁 관람");
  await checkPlan(page);
  const question = page.locator("[data-stop-question]");
  await expect(question).toBeVisible({ timeout: 40_000 });
  await question.getByRole("button", { name: /「올리브영 광화문점」으로 바꾸기/ }).click();
  await expect(question).toContainText("이동이 일정보다 39분 늦어요", { timeout: 15_000 });
  await question.getByRole("button", { name: /택시로 바꾸기/ }).click();
  await expect(bar(page)).toBeVisible({ timeout: 15_000 });
  await bar(page).getByRole("button", { name: "자동으로 넘어가지 않기" }).click();
});
