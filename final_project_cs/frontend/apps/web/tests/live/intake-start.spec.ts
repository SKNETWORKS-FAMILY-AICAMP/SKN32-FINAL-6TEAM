import { expect, test, type Page } from "@playwright/test";
import { mockServer, start } from "./helpers";
import { needsBadge } from "./plan-check-kit";

/**
 * `[2026-10-03 사용자 지시]` 「계획 확인하기」를 누르면 서버가 답하기를 기다리지 않고 곧바로 진행 화면(`/intakes/starting`)으로 넘어가고,
 * 서버가 접수 번호를 주면 그 접수의 화면에서 서버의 진행 알림(SSE)을 따라 이어진다. 테스트용 모방 서버로 도는 자동 시험(실제 서버 아님).
 */
const PLAN = "10/1 09:00 경복궁 관람\n12:00 광장시장 점심";
const LOADING = "여행 정보를 불러오고 있어요";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

/** 일반 불러오기 화면이 한 순간이라도 뜨면 기록해 둔다(마지막에 한 번 본다). 등록 화면이 처음 열릴 때 자기 글을 읽는 순간은 세지 않도록 누르기 직전에 `forgetLoadingScreen` 으로 지운다. */
async function watchForLoadingScreen(page: Page) {
  await page.addInitScript((phrase) => {
    (window as unknown as { __sawLoading: boolean }).__sawLoading = false;
    new MutationObserver(() => {
      if (document.body?.innerText.includes(phrase)) (window as unknown as { __sawLoading: boolean }).__sawLoading = true;
    }).observe(document, { childList: true, subtree: true, characterData: true });
  }, LOADING);
}
const sawLoadingScreen = (page: Page) => page.evaluate(() => (window as unknown as { __sawLoading: boolean }).__sawLoading);
const forgetLoadingScreen = (page: Page) => page.evaluate(() => { (window as unknown as { __sawLoading: boolean }).__sawLoading = false; });
/** 오류 문장 자리(`role=alert`) — 화면 이동을 알리는 Next 의 빈 알림은 세지 않는다. */
const planError = (page: Page) => page.locator("#plan-error");

async function fillAndSend(page: Page, text = PLAN) {
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(text);
  await expect(page.getByLabel("나의 여행 계획")).toHaveValue(text);
  await forgetLoadingScreen(page);
  await page.getByRole("button", { name: "계획 확인하기" }).click();
}

test("누르면 서버의 답을 기다리지 않고 곧바로 진행 화면으로 넘어가 올린 줄을 보이고, 서버가 받으면 그 접수의 실시간 진행으로 이어져 결과가 나온다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ intakeDelay: 2500, review: "on", board: "rich", intakeEvents: "on", readingPolls: 1 });
  await start(page);
  await watchForLoadingScreen(page);
  await fillAndSend(page);

  // 서버는 아직 답하지 않았다(2.5초): 등록 화면은 이미 사라지고, 진행 막대와 올린 줄과 「보내는 중」이 보인다
  await expect(page).toHaveURL(/\/intakes\/starting$/);
  await expect(page.getByLabel("나의 여행 계획")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "계획을 확인하고 있어요", level: 1 })).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "계획 확인 진행" })).toBeVisible();
  await expect(page.getByText("계획을 서버로 보내는 중이에요…")).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "10/1 09:00 경복궁 관람" })).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "12:00 광장시장 점심" })).toBeVisible();
  expect(await server.received("GET", "/events")).toHaveLength(0);              // 접수 번호가 없으니 실시간 진행도 아직 열지 않았다

  // 서버가 받으면 접수 번호의 화면으로 바뀌고(주소가 바뀐다), 서버의 진행 알림으로 이어져 결과가 나온다
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]{36}$/, { timeout: 15_000 });
  await expect(needsBadge(page)).toBeVisible({ timeout: 40_000 });
  expect((await server.received("GET", "/events")).length).toBeGreaterThan(0);
  expect((await server.received("POST", "/v1/web/trip-intakes")).length).toBe(1);
  expect(await sawLoadingScreen(page)).toBe(false);                             // 「여행 정보를 불러오고 있어요」 화면은 한 번도 뜨지 않았다
});

test("서버가 계획을 거절하면 등록 화면으로 돌아와 서버의 문장을 보이고, 쓴 글과 올리려던 파일이 그대로 있어 고쳐 다시 보낼 수 있다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ intakeRefusal: "계획 글이 너무 길어요 — 12,000자까지 읽어요", readingPolls: 0 });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await page.locator("#plan-files").setInputFiles({ name: "plan.txt", mimeType: "text/plain", buffer: Buffer.from("메모") });
  await page.getByRole("button", { name: "계획 확인하기" }).click();

  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(planError(page)).toContainText("계획 글이 너무 길어요");
  await expect(page.getByLabel("나의 여행 계획")).toHaveValue(PLAN);
  await expect(page.getByRole("list", { name: "선택한 파일" })).toContainText("plan.txt");

  // 글을 고치면 문장은 사라지고, 서버가 받아 주면 진행 화면을 거쳐 접수 화면으로 간다
  await server.scenario({ intakeRefusal: "" });
  await page.getByLabel("나의 여행 계획").fill("10/1 09:00 경복궁 관람");
  await expect(planError(page)).toHaveCount(0);
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]{36}$/, { timeout: 15_000 });
  expect((await server.received("POST", "/v1/web/trip-intakes")).length).toBe(2);
});

test("보내는 중에 뒤로 가기 화살표를 누르면 등록 화면으로 돌아가 글이 그대로 있고, 오류 문장은 뜨지 않는다", async ({ page, request }) => {
  await mockServer(request).scenario({ intakeDelay: 4000, readingPolls: 0 });
  await start(page);
  await fillAndSend(page);
  await expect(page).toHaveURL(/\/intakes\/starting$/);
  await page.getByRole("button", { name: "뒤로" }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(page.getByLabel("나의 여행 계획")).toHaveValue(PLAN);
  await expect(planError(page)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "계획 확인하기" })).toBeEnabled();
  // 서버가 늦게 답해도 화면은 끌려가지 않는다
  await page.waitForTimeout(4500);
  await expect(page).toHaveURL(/\/trips\/new$/);
});

test("보내는 중에 새로고침하면(보내던 계획은 메모리에만 있어 사라진다) 등록 화면으로 돌아가고, 쓴 글은 그대로다", async ({ page, request }) => {
  await mockServer(request).scenario({ intakeDelay: 4000, readingPolls: 0 });
  await start(page);
  await fillAndSend(page);
  await expect(page).toHaveURL(/\/intakes\/starting$/);
  await page.reload();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(page.getByLabel("나의 여행 계획")).toHaveValue(PLAN);
});

test("세션이 없는 첫 방문도 누르는 순간 진행 화면으로 넘어가고, 게스트 세션은 그 사이에 만들어진다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ intakeDelay: 1500, review: "on", board: "rich", readingPolls: 1 });
  await start(page, null);
  await fillAndSend(page);
  await expect(page).toHaveURL(/\/intakes\/starting$/);
  await expect(page.getByText("계획을 서버로 보내는 중이에요…")).toBeVisible();
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]{36}$/, { timeout: 15_000 });
  await expect(needsBadge(page)).toBeVisible({ timeout: 40_000 });
  expect((await server.received("POST", "/v1/web/auth/session")).length).toBe(1);
  // 키 안내는 어디에도 없다
  await expect(page.getByText("내 여행 열쇠를 따로 보관해 주세요")).toHaveCount(0);
});

test("서버가 몇 초 넘게 답이 없으면 진행 화면이 「서버가 답하는 데 시간이 걸리고 있어요」라고 알리고, 답이 오면 그대로 이어진다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ intakeDelay: 6500, review: "on", board: "rich", readingPolls: 1 });
  await start(page);
  await fillAndSend(page);
  await expect(page).toHaveURL(/\/intakes\/starting$/);
  await expect(page.getByText("계획을 서버로 보내는 중이에요…")).toBeVisible();
  await expect(page.getByText("서버가 답하는 데 시간이 걸리고 있어요")).toBeVisible({ timeout: 8_000 });     // 4초쯤 뒤
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]{36}$/, { timeout: 15_000 });
  await expect(needsBadge(page)).toBeVisible({ timeout: 40_000 });
});
