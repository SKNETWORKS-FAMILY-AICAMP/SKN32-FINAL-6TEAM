import { expect, test, type Page } from "@playwright/test";
import { checkPlan, mockServer, start } from "./helpers";

/**
 * `[2026-10-20 사용자 결정 — 계획 확인 C안]` 첫 검사는 확인이 필요한 카드에서 멈춰 그 카드 안에서 묻고, 고르면 그 자리에서 다시 확인한 뒤 이어 간다
 * (흐름 목업 `mockups/tripilot-plan-flow-register.html` 4단계) — 테스트용 모방 서버로 도는 자동 시험(실제 서버 아님).
 * 모방 서버의 `board: "rich"` 는 올리브영이 「이름이 여러 곳이라 가까운 곳을 임시로」(`picked_nearest`) 고른 확인 필요 일정이다.
 */
const card = (page: Page, title: string) => page.getByRole("article", { name: title });
const question = (page: Page) => page.locator("[data-stop-question]");
const banner = (page: Page) => page.locator("[data-stop-banner]");
const body = (page: Page) => page.locator('[class*="sheetBody"]').first();

async function stopped(page: Page, request: Parameters<typeof mockServer>[0], change: Record<string, unknown> = {}) {
  const server = mockServer(request);
  await server.reset();
  await server.scenario({ review: "on", board: "rich", intakeEvents: "on", readingPolls: 1, ...change });
  await start(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill("10/1 09:00 경복궁 관람");
  await checkPlan(page);
  await expect(question(page)).toBeVisible({ timeout: 40_000 });
  return server;
}

/** How far (px) the stopped card stands under the banner. */
const underBanner = (page: Page) => page.evaluate(() => {
  const focus = document.querySelector<HTMLElement>("li[data-stop-focus]")!.getBoundingClientRect();
  const top = document.querySelector<HTMLElement>("[data-stop-banner]")!.getBoundingClientRect();
  return Math.round(focus.top - top.bottom);
});

test("확인이 필요한 카드에서 멈춰 안내 · 질문을 보이고, 나머지는 흐리게 두며 결과 화면으로 넘어가지 않는다", async ({ page, request }) => {
  await stopped(page, request);
  await expect(banner(page)).toContainText("이 일정이 맞는지 먼저 확인해 주세요");
  await expect(banner(page)).toContainText("고치면 다음 일정을 이어서 확인해요 · 남은 일정 1곳");
  await expect(question(page)).toContainText("「올리브영」은 맞는 곳이 3곳이라 가까운 「올리브영 인사동점」으로 임시로 골랐어요. 어디로 갈까요?");
  await expect(question(page).getByRole("button", { name: /「올리브영 인사동점」 그대로/ })).toBeVisible();
  await expect(question(page).getByRole("button", { name: /「올리브영 광화문점」으로 바꾸기/ })).toContainText("이유:");
  await expect(question(page).getByRole("button", { name: "직접 수정" })).toBeVisible();
  await expect(question(page).getByRole("button", { name: "삭제" })).toHaveCount(0);                 // 일정 추가 · 삭제는 등록 뒤 수정 모드에서만
  // 멈춘 카드만 또렷하고 나머지(카드 · 이동 · 레일)는 흐리다. 확인 전 카드는 점선.
  await expect(page.locator('li[data-entry-id="0-1"]')).toHaveAttribute("data-stop-focus", "true");
  await expect(page.locator('li[data-entry-id="0-0"]')).toHaveCSS("opacity", "0.38");
  await expect(page.locator('li[data-entry-id="0-2"]')).toHaveAttribute("data-reveal-waiting", "true");
  await expect(page.locator('li[data-entry-id="0-2"] article')).toHaveCSS("border-top-style", "dashed");
  await expect.poll(() => underBanner(page)).toBeGreaterThanOrEqual(10);
  await expect.poll(() => underBanner(page)).toBeLessThanOrEqual(18);
  // 멈춘 동안에는 결과 화면이 아니다.
  await page.waitForTimeout(2_000);
  await expect(page.locator('main[data-stage="checking"]')).toBeVisible();
  await expect(page.getByRole("button", { name: "여행 등록" })).toHaveCount(0);
});

test("고르면 질문이 접히고 그 카드가 그 자리에서 다시 확인된 뒤 이어 간다 — 알림 없이, 화면 읽기 줄로만", async ({ page, request }) => {
  const server = await stopped(page, request);
  const toasts: string[] = [];
  await page.exposeFunction("zzNoticed", (text: string) => { toasts.push(text); });
  await page.evaluate(() => new MutationObserver(() => document.querySelectorAll('[class*="toast-view-module"]')
    .forEach((node) => (window as unknown as { zzNoticed: (text: string) => void }).zzNoticed(node.textContent ?? ""))).observe(document.body, { subtree: true, childList: true }));
  await question(page).getByRole("button", { name: /「올리브영 광화문점」으로 바꾸기/ }).click();
  await expect(banner(page)).toContainText("다시 확인하는 중이에요 · 잠시만요");
  await expect(card(page, "올리브영 광화문점")).toContainText("원문 「올리브영」");
  await expect(page.locator('main[data-stage="done"]')).toBeVisible({ timeout: 15_000 });
  expect(toasts).toEqual([]);
  await expect(page.locator('main p.sr-only[role="status"]')).toHaveText(/확인을 마쳤어요/);
  // 흐름 안에서 고른 것은 검사까지 하는 기본 저장(`check:false` 없음)으로 보낸다.
  const [sent] = await server.received("POST", "/edits");
  expect(sent.body).toMatchObject({ revision: 1 });
  expect((sent.body as { check?: boolean }).check).toBeUndefined();
});

test("질문 칸을 보려고 내린 채 골라도 목록이 멈췄던 카드 자리로 돌아와 다시 확인이 보인다", async ({ page, request }) => {
  await stopped(page, request);
  const before = await underBanner(page);
  const option = question(page).getByRole("button", { name: /「올리브영 종각점」으로 바꾸기/ });
  await body(page).evaluate((element) => { element.scrollTop = element.scrollHeight; });
  await option.click();
  await expect(banner(page)).toContainText("다시 확인하는 중이에요");
  await expect.poll(async () => Math.abs((await underBanner(page)) - before), { timeout: 3_000 }).toBeLessThanOrEqual(4);
});

test("서버가 고른 것을 거절하면 그 말을 닫을 때까지 남기고, 카드와 질문은 그대로 다시 묻는다", async ({ page, request }) => {
  await stopped(page, request, { edits: "not_found" });
  await question(page).getByRole("button", { name: /「올리브영 광화문점」으로 바꾸기/ }).click();
  await expect(page.getByRole("alert").filter({ hasText: "이 이름으로 장소를 찾지 못했어요" })).toBeVisible();
  await expect(question(page)).toBeVisible();
  await expect(banner(page)).toContainText("이 일정이 맞는지 먼저 확인해 주세요");
  await expect(card(page, "올리브영")).toContainText("이름이 여러 곳이라 가까운 「올리브영 인사동점」으로 임시로 골랐어요");
});

test("「직접 수정」은 그 일정의 바꾸기 화면을 열고, 거기서 고르면 흐름으로 돌아와 다시 확인한 뒤 이어 간다", async ({ page, request }) => {
  await stopped(page, request);
  await question(page).getByRole("button", { name: "직접 수정" }).click();
  await expect(page.getByRole("button", { name: "바꾸기 그만두기" })).toBeVisible();
  await page.getByRole("button", { name: "이 장소로 바꾸기" }).first().click();
  await expect(page.locator('main[data-stage="done"]')).toBeVisible({ timeout: 15_000 });
});
