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
  await server.scenario({ review: "on", board: "rich", intakeEvents: "on", readingPolls: 1, moveOptions: "on", ...change });
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
  await expect(question(page).getByRole("button", { name: "삭제", exact: true })).toBeVisible();       // `[2026-10-20 사용자 재결정]` 질문 칸에도 삭제(한 번 묻고)
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

test("고르면 질문이 접히고 그 카드가 그 자리에서 다시 확인된 뒤 이어 간다 — 알림 없이, 화면 읽기 줄로만 (오는 길이 늦으면 같은 카드에서 「도착」을 묻는다)", async ({ page, request }) => {
  const server = await stopped(page, request);
  const toasts: string[] = [];
  await page.exposeFunction("zzNoticed", (text: string) => { toasts.push(text); });
  await page.evaluate(() => new MutationObserver(() => document.querySelectorAll('[class*="toast-view-module"], [class$="_toast"], [class*="_toast "]')
    .forEach((node) => (window as unknown as { zzNoticed: (text: string) => void }).zzNoticed(node.textContent ?? ""))).observe(document.body, { subtree: true, childList: true }));
  await question(page).getByRole("button", { name: /「올리브영 광화문점」으로 바꾸기/ }).click();
  await expect(banner(page)).toContainText("다시 확인하는 중이에요 · 잠시만요");
  await expect(card(page, "올리브영 광화문점")).toContainText("원문 「올리브영」");
  // `[2026-10-20 이동 확인 C안]` 장소는 통과했지만 경복궁 관람에서 오는 길이 늦다(모방 서버 판 −39분): 같은 카드에서 묻는다.
  await expect(question(page)).toContainText("「경복궁 관람 → 올리브영 광화문점」 이동이 일정보다 39분 늦어요. 어떻게 할까요?", { timeout: 15_000 });
  await expect(question(page)).toContainText("도착");
  await expect(question(page)).not.toContainText("고른 뒤에도 확인이 필요해요");                      // 장소 다음의 도착은 새 질문이다
  await expect(page.locator('li[data-entry-id="0-1"]')).toHaveAttribute("data-stop-focus", "true");
  await question(page).getByRole("button", { name: /택시로 바꾸기/ }).click();
  await expect(page.locator('main[data-stage="done"]')).toBeVisible({ timeout: 15_000 });
  expect(toasts).toEqual([]);
  expect(await server.received("POST", "~0-1/mode")).toHaveLength(1);
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
  await expect(question(page)).toContainText("이동이 일정보다 39분 늦어요", { timeout: 15_000 });        // 장소는 통과 — 이어서 그 카드의 도착을 묻는다
});

test("`[2026-10-20 이동 확인 C안]` 오는 길이 늦을 때 「늦추기」를 고르면 그 일정 시작을 서버가 맞춘 시각으로 바꾸고 이어 간다", async ({ page, request }) => {
  const server = await stopped(page, request);
  await question(page).getByRole("button", { name: /「올리브영 인사동점」 그대로/ }).click();
  const later = question(page).getByRole("button", { name: /시작으로 늦추기/ });
  await expect(later).toBeVisible({ timeout: 15_000 });
  await expect(later).toContainText("「올리브영 인사동점」 11:40 시작으로 늦추기");          // 고른 곳이 카드 이름이 된다
  await later.click();
  await expect(page.locator('main[data-stage="done"]')).toBeVisible({ timeout: 15_000 });
  const edits = await server.received("POST", "/edits");
  expect(edits.at(-1)!.body).toMatchObject({ edits: expect.arrayContaining([expect.objectContaining({ field: "items[1].starts_at", value: "11:40" })]) });
});

test("「직접 수정」으로 늦은 도착을 고치면 그 일정의 직접 고치기가 열린다", async ({ page, request }) => {
  await stopped(page, request);
  await question(page).getByRole("button", { name: /「올리브영 인사동점」 그대로/ }).click();
  await expect(question(page)).toContainText("이동이 일정보다 39분 늦어요", { timeout: 15_000 });
  await question(page).getByRole("button", { name: "직접 수정" }).click();
  await expect(page.getByRole("form", { name: "「올리브영 인사동점」 고치기" })).toBeVisible();
  await expect(page.getByLabel("시작")).toBeVisible();
});

test("「애니메이션 건너뛰기」여도 확인이 필요한 카드까지 바로 그리고 멈춰 묻는다", async ({ page, request }) => {
  await page.addInitScript(() => localStorage.setItem("tripilot.web.settings.v1", JSON.stringify({ language: "ko", skipAnimation: true })));
  await stopped(page, request);
  await expect(page.locator('li[data-entry-id="0-2"]')).toHaveAttribute("data-reveal-waiting", "true");
  await question(page).getByRole("button", { name: /「올리브영 광화문점」으로 바꾸기/ }).click();
  await expect(question(page)).toContainText("이동이 일정보다 39분 늦어요", { timeout: 15_000 });
  await question(page).getByRole("button", { name: /택시로 바꾸기/ }).click();
  await expect(page.locator('main[data-stage="done"]')).toBeVisible({ timeout: 15_000 });
});

test("시스템의 「동작 줄이기」여도 같은 순서로 멈추고 이어 간다", async ({ page, request }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await stopped(page, request);
  await question(page).getByRole("button", { name: /「올리브영 광화문점」으로 바꾸기/ }).click();
  await expect(question(page)).toContainText("이동이 일정보다 39분 늦어요", { timeout: 15_000 });
});

// `[2026-10-20 사용자 결정 — 다시 들어오면 결과 화면]` 등록 전에 화면을 떠났다가(창 닫기 · 뒤로 가기 · 새로고침) 다시 들어오면 멈추지 않고 예전처럼 결과 화면 — 결과 화면이 고치는 자리다.
// `[2026-10-21 사용자 지시 — 결과 화면의 「확인 필요」 카드에도 검증 때 질문 칸 그대로]` 멈추지는 않지만, 확인이 필요한 카드 안에 첫 검사 때와 같은 질문 칸(선택지 · 직접 수정 · 삭제)이 있다.
async function reopened(page: Page, request: Parameters<typeof mockServer>[0]) {
  const server = mockServer(request);
  await server.reset();
  await server.scenario({ review: "on", board: "rich", readingPolls: 0, moveOptions: "on" });
  await start(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/intakes/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee");
  await expect(page.locator('main[data-stage="done"]')).toBeVisible({ timeout: 15_000 });
  return server;
}
const asked = (page: Page, title: string) => card(page, title).locator("[data-stop-question]");

test("검사가 끝난 접수를 다시 열면 멈추지 않고 결과 화면을 보인다 — 확인 필요 카드 안에는 첫 검사 때와 같은 질문 칸이 있다", async ({ page, request }) => {
  await reopened(page, request);
  await expect(page.getByRole("button", { name: /^확인 필요 \d+곳$/ })).toBeVisible();
  await expect(banner(page)).toHaveCount(0);                                                         // 멈추지 않는다 — 안내 줄 · 흐리게 없음
  await expect(page.locator("li[data-stop-focus]")).toHaveCount(0);
  await expect(card(page, "올리브영")).toContainText("확인 필요");
  await expect(asked(page, "올리브영")).toContainText("「올리브영」은 맞는 곳이 3곳이라 가까운 「올리브영 인사동점」으로 임시로 골랐어요. 어디로 갈까요?");
  await expect(asked(page, "올리브영").getByRole("button", { name: /「올리브영 인사동점」 그대로/ })).toBeVisible();
  await expect(asked(page, "올리브영").getByRole("button", { name: /「올리브영 광화문점」으로 바꾸기/ })).toContainText("이유:");
  await expect(asked(page, "올리브영").getByRole("button", { name: "직접 수정" })).toBeVisible();
  await expect(asked(page, "올리브영").getByRole("button", { name: "삭제", exact: true })).toBeVisible();
  await expect(question(page)).toHaveCount(1);                                                       // 확인이 필요한 카드에만
});

test("결과 화면의 질문 칸에서 고르면 검사까지 함께 저장하고 그 카드가 새 판으로 바뀐다 — 오는 길이 늦으면 같은 카드에서 「도착」을 묻는다", async ({ page, request }) => {
  const server = await reopened(page, request);
  await asked(page, "올리브영").getByRole("button", { name: /「올리브영 광화문점」으로 바꾸기/ }).click();
  await expect(card(page, "올리브영 광화문점")).toContainText("원문 「올리브영」", { timeout: 15_000 });
  const [sent] = await server.received("POST", "/edits");
  expect((sent.body as { check?: boolean }).check).toBeUndefined();                                  // 검사 포함 저장 — 「다시 제출」 대상이 아니다
  await expect(asked(page, "올리브영 광화문점")).toContainText("「경복궁 관람 → 올리브영 광화문점」 이동이 일정보다 39분 늦어요. 어떻게 할까요?");
  await expect(asked(page, "올리브영 광화문점").getByRole("button", { name: "삭제", exact: true })).toHaveCount(0);
  await asked(page, "올리브영 광화문점").getByRole("button", { name: /택시로 바꾸기/ }).click();
  await expect.poll(async () => (await server.received("POST", "~0-1/mode")).length).toBe(1);
  await expect(question(page)).toHaveCount(0, { timeout: 15_000 });
  await expect(page.getByRole("button", { name: "다시 제출" })).toHaveCount(0);
});

test("결과 화면의 질문 칸 「삭제」도 한 번 묻고, 지우면 검사까지 함께 저장한다", async ({ page, request }) => {
  const server = await reopened(page, request);
  await asked(page, "올리브영").getByRole("button", { name: "삭제", exact: true }).click();
  await page.getByRole("alertdialog", { name: "「올리브영」 일정을 삭제할까요?" }).getByRole("button", { name: "삭제", exact: true }).click();
  await expect(card(page, "올리브영")).toHaveCount(0, { timeout: 15_000 });
  const [sent] = await server.received("POST", "/edits");
  expect(sent.body).toMatchObject({ edits: [{ field: "items[1].removed", value: true }] });
  expect((sent.body as { check?: boolean }).check).toBeUndefined();
});

test("결과 화면의 질문 칸 「직접 수정」은 바꾸기 화면을 열고, 거기서 고르면 검사까지 함께 저장한다", async ({ page, request }) => {
  const server = await reopened(page, request);
  await asked(page, "올리브영").getByRole("button", { name: "직접 수정" }).click();
  await page.getByRole("button", { name: "이 장소로 바꾸기" }).first().click();
  await expect.poll(async () => (await server.received("POST", "/edits")).length, { timeout: 15_000 }).toBe(1);
  const [sent] = await server.received("POST", "/edits");
  expect((sent.body as { check?: boolean }).check).toBeUndefined();
});

test("멈춘 동안 고른 것은 바로 서버에 저장돼, 그 뒤 새로고침하면 고친 그대로 결과 화면에 보인다", async ({ page, request }) => {
  await stopped(page, request);
  await question(page).getByRole("button", { name: /「올리브영 광화문점」으로 바꾸기/ }).click();
  await expect(question(page)).toContainText("이동이 일정보다 39분 늦어요", { timeout: 15_000 });     // 장소는 고쳤고, 도착을 묻는 중
  await page.reload();
  await expect(page.locator('main[data-stage="done"]')).toBeVisible({ timeout: 15_000 });
  await expect(banner(page)).toHaveCount(0);
  await expect(card(page, "올리브영 광화문점")).toBeVisible();                                         // 고친 장소는 서버에 있다
  // `[2026-10-21]` 남은 늦은 도착은 결과 화면의 그 카드에서 같은 질문 칸으로 묻는다
  await expect(card(page, "올리브영 광화문점").locator("[data-stop-question]")).toContainText("이동이 일정보다 39분 늦어요");
});

test("`[2026-10-20 사용자 재결정]` 질문 칸의 「삭제」는 한 번 묻고, 지우면 그 일정을 빼고 다음 일정을 이어서 확인한다", async ({ page, request }) => {
  const server = await stopped(page, request);
  await question(page).getByRole("button", { name: "삭제", exact: true }).click();
  const dialog = page.getByRole("alertdialog", { name: "「올리브영」 일정을 삭제할까요?" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "취소" }).click();
  await expect(dialog).toHaveCount(0);
  expect(await server.received("POST", "/edits")).toHaveLength(0);                                   // 취소하면 아무것도 보내지 않는다
  await question(page).getByRole("button", { name: "삭제", exact: true }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "삭제", exact: true }).click();
  await expect(page.locator('main[data-stage="done"]')).toBeVisible({ timeout: 15_000 });
  await expect(card(page, "올리브영")).toHaveCount(0);
  const [sent] = await server.received("POST", "/edits");
  expect(sent.body).toMatchObject({ edits: [{ field: "items[1].removed", value: true }] });
  expect((sent.body as { check?: boolean }).check).toBeUndefined();                                  // 검사 포함으로 보낸다
});

test("늦은 도착을 묻는 질문 칸에는 「삭제」가 없다 — 고칠 것은 오는 길이다", async ({ page, request }) => {
  await stopped(page, request);
  await question(page).getByRole("button", { name: /「올리브영 인사동점」 그대로/ }).click();
  await expect(question(page)).toContainText("이동이 일정보다 39분 늦어요", { timeout: 15_000 });
  await expect(question(page).getByRole("button", { name: "삭제", exact: true })).toHaveCount(0);
});

// `[2026-10-21 사용자 지적 — 멈춘 질문 칸이 「후보를 찾는 중…」에 오래 머묾]` 「확인 필요」 판정이 그려지면 그 일정의 후보를 미리 부르고, 멈춘 질문은 그 요청을 같이 쓴다.
//   첫 검사를 그리는 동안(질문에서 멈춘 동안 포함)은 「전체 자동 추천」 미리 계산(일정 지정 없는 autofix)을 부르지 않는다.
test("멈춘 질문의 후보는 미리 부른 요청 하나를 같이 쓰고, 질문 칸이 열려 있는 동안 「전체 자동 추천」 미리 계산을 부르지 않는다", async ({ page, request }) => {
  const server = await stopped(page, request);
  await expect(question(page).getByRole("button", { name: /「올리브영 광화문점」으로 바꾸기/ })).toBeVisible();
  const asks = (await server.received("GET", "/candidates")).filter((entry) => entry.query?.includes("index=1"));
  expect(asks).toHaveLength(1);
  const warm = (await server.received("POST", "/autofix")).filter((entry) => !(entry.body as { item_id?: string } | null)?.item_id);
  expect(warm).toHaveLength(0);
});

// `[2026-10-21 사용자 지적 — 멈춘 동안 「…확인이 오래 걸리고 있어요」 알림]` 확인이 필요한 카드에서 검사가 서버의 끝을 기다리며 멈춘 동안(서버는 뒤 일정을 아직 검사 중)에는
//   서버가 늦다 · 소식이 없다는 알림을 띄우지 않는다 — 고객이 기다리는 것은 그 카드의 질문이다. 멈출 카드가 없으면 전처럼 띄운다.
async function heldCheck(page: Page, request: Parameters<typeof mockServer>[0], board: "rich" | "calm") {
  const server = mockServer(request);
  await server.reset();
  await server.scenario({ review: "on", board, intakeEvents: "held", readingPolls: 999 });
  await start(page);
  const said: string[] = [];
  await page.exposeFunction("zzNoticed", (text: string) => { said.push(text); });
  // 알림 상자의 클래스 이름은 빌드에서 바뀐다 — 화면 글자에 그 문장이 나타났는지 본다
  await page.addInitScript(() => {
    addEventListener("DOMContentLoaded", () => new MutationObserver(() => {
      const text = document.body.textContent ?? "";
      for (const words of ["서버 소식이 한동안 없어요", "1분이 넘게 서버 소식이 없어요", "서버 응답이 늦어지고 있어요", "오래 걸리고 있어요"]) if (text.includes(words)) (window as unknown as { zzNoticed: (text: string) => void }).zzNoticed(words);
    }).observe(document.body, { subtree: true, childList: true, characterData: true }));
  });
  await page.clock.install();
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill("10/1 09:00 경복궁 관람");
  await checkPlan(page);
  await expect(page.locator('main[data-stage="checking"]')).toBeVisible({ timeout: 15_000 });
  for (let waited = 0; waited < 40_000; waited += 1_000) await page.clock.runFor(1_000);
  await page.waitForTimeout(300);
  return said;
}

test("확인이 필요한 카드에서 서버의 끝을 기다리며 멈춘 동안에는 「서버 소식이 한동안 없어요」를 띄우지 않는다", async ({ page, request }) => {
  test.setTimeout(90_000);
  const said = await heldCheck(page, request, "rich");
  await expect(page.locator('li[data-entry-id="0-1"]')).toHaveAttribute("data-verdict", "checking");  // 올리브영의 판정을 기다리며 멈춰 있다
  await expect(page.locator('li[data-entry-id="0-2"]')).toHaveAttribute("data-reveal-waiting", "true");  // 다음 카드는 점선으로 기다린다
  expect(said.filter((text) => /서버 소식이|늦어지고 있어요|오래 걸리고 있어요/.test(text))).toEqual([]);
});

test("멈출 카드 없이 서버를 기다리면 전처럼 「서버 소식이 한동안 없어요」를 띄운다", async ({ page, request }) => {
  test.setTimeout(90_000);
  const said = await heldCheck(page, request, "calm");
  expect(said.some((text) => text.includes("서버 소식이 한동안 없어요"))).toBe(true);
});

// `[2026-10-21 사용자 지적 — 「확인 중인 곳으로」가 목록 맨 위에 붙어 내리면 가려진다]` 단추는 목록 위에 떠 있어 어디로 내려도 시트 아래쪽 같은 자리에 보이고, 누르면 확인 중인 곳을 다시 따라간다.
test("검사 중 목록을 내려도 「확인 중인 곳으로」는 시트 아래쪽에 떠 있고, 누르면 다시 따라간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.reset();
  await server.scenario({ review: "on", board: "rich", intakeEvents: "held", readingPolls: 999 });
  await start(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill("10/1 09:00 경복궁 관람");
  await checkPlan(page);
  await expect(page.locator('li[data-entry-id="0-1"]')).toBeVisible({ timeout: 20_000 });
  const pill = page.getByRole("button", { name: "확인 중인 곳으로" });
  const sheet = page.locator("section[aria-labelledby='plan-check-sheet-title']");
  await body(page).hover();
  await page.mouse.wheel(0, 300);
  await expect(pill).toBeVisible();
  const sheetBox = (await sheet.boundingBox())!;
  const first = (await pill.boundingBox())!;
  expect(sheetBox.y + sheetBox.height - (first.y + first.height)).toBeGreaterThanOrEqual(8);      // 시트 아래쪽 안에 떠 있다
  expect(sheetBox.y + sheetBox.height - (first.y + first.height)).toBeLessThanOrEqual(24);
  await page.mouse.wheel(0, 600);
  await page.waitForTimeout(300);
  expect((await pill.boundingBox())!.y).toBeCloseTo(first.y, 0);                                  // 더 내려도 같은 자리
  await page.mouse.wheel(0, -900);
  await page.waitForTimeout(300);
  expect((await pill.boundingBox())!.y).toBeCloseTo(first.y, 0);                                  // 올려도 같은 자리
  await pill.click();
  await expect(pill).toHaveCount(0);
});

// `[2026-10-21 사용자 지적 — 「호텔 조식」 후보 1 · 2번이 같은 호텔]` 서버는 숙소와 그 숙소 안 식사를 짝으로 준다 — 질문 칸 선택지에도 바꾸기 화면과 같은 꼬리표가 붙어 둘을 가른다.
test("질문 칸의 후보 선택지에는 바꾸기 화면과 같은 꼬리표(숙소 · 숙소 안 식사)가 붙는다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.reset();
  await server.scenario({ review: "on", board: "rich", readingPolls: 0, candidateBasis: "lodging" });
  await start(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/intakes/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee");
  await expect(page.locator('main[data-stage="done"]')).toBeVisible({ timeout: 15_000 });
  const options = asked(page, "올리브영").getByRole("button", { name: /바꾸기/ });
  await expect(options.first()).toBeVisible({ timeout: 15_000 });
  await expect(options.nth(0)).toContainText("숙소");
  await expect(options.nth(0)).not.toContainText("숙소 안 식사");
  await expect(options.nth(1)).toContainText("숙소 안 식사");
});
