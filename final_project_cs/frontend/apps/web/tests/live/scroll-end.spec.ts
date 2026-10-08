import { expect, test, type Page } from "@playwright/test";
import { mockServer, start } from "./helpers";
import { needsBadge } from "./plan-check-kit";

/**
 * `[2026-10-05 사용자 선택 — 스크롤 끝 안 A]` 계획 확인 화면의 목록 맨 끝: 권장 수정안이 없으면 「계속 내리면 …」 표시는 꺼지고 이유를 말하고,
 * 더 밀어도 화면이 위로 튀지 않고 그 자리에서 흔들리며 알림은 한 번만 뜬다. 테스트용 모방 서버로 도는 자동 시험(실제 서버 아님).
 */
const INTAKE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

async function openFinished(page: Page, request: Parameters<typeof mockServer>[0], change: Record<string, unknown> = {}) {
  const server = mockServer(request);
  await server.scenario({ review: "on", board: "rich", readingPolls: 0, ...change });
  await start(page);
  await page.goto(`/intakes/${INTAKE}`);
  await expect(needsBadge(page)).toBeVisible();
  return server;
}

const hint = (page: Page) => page.getByRole("button", { name: /권장 수정안이 없어서/ });

test("권장 수정안이 없으면 맨 끝 표시는 처음부터 꺼져 있고 이유를 말한다 (서버를 다시 부르지 않는다)", async ({ page, request }) => {
  const server = await openFinished(page, request, { autofix: "none" });
  await expect(hint(page)).toBeVisible();
  await expect(hint(page)).toHaveAttribute("aria-disabled", "true");
  await expect(page.getByText("계속 내리면 권장 수정안이 반영된 모습을 보여 드려요")).toHaveCount(0);
  expect((await server.received("POST", "/autofix")).length).toBe(1);                  // 화면이 열릴 때 받아 둔 한 번뿐
});

test("꺼진 표시를 누르면 화면은 그 자리에 있고, 흔들리며 알림이 한 번만 뜬다 — 알림이 있는 동안 또 눌러도 겹치지 않는다", async ({ page, request }) => {
  await openFinished(page, request, { autofix: "none" });
  const body = page.locator("[data-entry-id]").first().locator("xpath=ancestor::div[contains(@class,'sheetBody')][1]");
  await hint(page).scrollIntoViewIfNeeded();
  const before = await body.evaluate((element) => element.scrollTop);
  await hint(page).click({ force: true });                                              // aria-disabled 단추는 Playwright 가 기본으로는 누르지 않는다
  await expect(page.getByRole("status").filter({ hasText: "권장 수정안이 없어요" })).toBeVisible();
  await expect(page.locator("[data-shake]")).toHaveCount(1);
  await expect(page.locator("[data-shake]")).toHaveCount(0, { timeout: 2000 });         // 흔들림은 잠깐이다
  await hint(page).click({ force: true });                                              // 알림이 떠 있는 동안 또 눌러도
  await expect(page.locator("[data-shake]")).toHaveCount(0);                            // 다시 흔들리지 않는다
  expect(await body.evaluate((element) => element.scrollTop)).toBe(before);             // 위로 튀지 않았다
  await expect(page.getByRole("status").filter({ hasText: "권장 수정안이 없어요" })).toHaveCount(1);
});

test("끝에서 더 밀어도 화면은 위로 튀지 않고 그 자리에서 흔들리며 알림만 뜬다 (사용자가 직접 고쳐야 하는 곳으로 끌고 가지 않는다)", async ({ page, request }) => {
  const server = await openFinished(page, request, { autofix: "none" });
  const olive = page.getByRole("article", { name: "올리브영" });
  await hint(page).scrollIntoViewIfNeeded();
  const body = page.locator("[data-entry-id]").first().locator("xpath=ancestor::div[contains(@class,'sheetBody')][1]");
  await body.hover();
  await page.waitForTimeout(500);                                                       // 끝에 닿은 스크롤이 가라앉은 뒤의 밀기만 센다
  const before = await body.evaluate((element) => element.scrollTop);
  for (let push = 0; push < 6; push += 1) { await page.mouse.wheel(0, 60); await page.waitForTimeout(40); }
  await expect(page.getByRole("status").filter({ hasText: "권장 수정안이 없어요" })).toBeVisible();
  expect(await body.evaluate((element) => element.scrollTop)).toBeGreaterThanOrEqual(before - 2);
  await expect(olive.getByRole("button", { name: "올리브영", exact: true })).toHaveAttribute("aria-expanded", "false");   // 고칠 곳을 열지도 않았다
  expect((await server.received("POST", "/edits")).length).toBe(0);
});

test("권장 수정안이 있으면 표시는 그대로이고 누르면 수정안이 열린다 (꺼지지 않는다)", async ({ page, request }) => {
  await openFinished(page, request);
  await expect(page.getByText("계속 내리면 권장 수정안이 반영된 모습을 보여 드려요")).toBeVisible();
  await expect(hint(page)).toHaveCount(0);
});
