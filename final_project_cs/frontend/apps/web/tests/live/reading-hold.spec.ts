import { expect, test, type Page } from "@playwright/test";
import { checkPlan, mockServer, openRegistration, start } from "./helpers";

/**
 * `[2026-10-07 사용자 지적 — 로딩이 끝난 화면에서 뒤로 갔다가 「계획 확인하기」를 다시 누르면 읽는 화면(tj)과 확인 화면(tM)이 번갈아 나온다]` 질문이 붙은 계획은 서버가 확인하는 동안 확인 화면이 먼저 뜨고,
 * 서버가 끝나는 순간 질문 때문에 읽는 화면으로 되끌려 갔다가 몇 초 뒤 확인 화면이 처음부터 다시 그려졌다. 이제 질문이 화면에 있는 동안은 읽는 화면이 그대로 있고(진행 막대만 움직인다), 보내 주면 확인 화면으로 한 번만 간다.
 * 이미 읽은 계획을 다시 열면(뒤로 · 앞으로, 목록) 붙잡을 것이 없으니 곧장 확인 화면이다. mock 서버 시험이다 — 화면 반응을 본다.
 */
const PLAN = "10/1 09:00 경복궁 관람";
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); await mockServer(request).scenario({ questions: "two" }); });

/** 50ms 마다 어느 화면인지 적는다: 읽는 화면(제목이 보이는 「계획을 확인하고 있어요」) ↔ 확인 화면. */
async function watch(page: Page, ms: number) {
  await page.evaluate((span) => {
    const w = window as unknown as { __screens: string[] };
    w.__screens = [];
    const t0 = performance.now();
    let last = "";
    const id = setInterval(() => {
      const reading = Array.from(document.querySelectorAll("h1")).some((h) => !h.classList.contains("sr-only") && (h.textContent ?? "").includes("계획을 확인하고 있어요"));
      const screen = document.querySelector('[data-device] [data-stage][data-replay]') as HTMLElement | null;
      const now = `${reading ? "읽는 화면" : "확인 화면"}(${screen?.getAttribute("data-stage") ?? "-"})`;
      if (now !== last) { w.__screens.push(`${Math.round(performance.now() - t0)}ms ${now}`); last = now; }
    }, 50);
    setTimeout(() => clearInterval(id), span);
  }, ms);
}
const screens = (page: Page) => page.evaluate(() => (window as unknown as { __screens: string[] }).__screens);
/** 읽는 화면 ↔ 확인 화면 으로 오간 횟수에서 「확인 → 읽는」 으로 되돌아간 것. */
const backToReading = (log: string[]) => log.map((entry) => entry.includes("읽는 화면")).reduce((count, reading, index, all) => count + (reading && index > 0 && all.slice(0, index).some((was) => !was) ? 1 : 0), 0);

// ★한계(2026-10-07 확인): mock 서버의 읽기 줄기는 읽는 동안 확인 진행(장소 · 이동 확인) 이벤트를 보내지 않아서, 「서버가 확인하는 동안 확인 화면이 먼저 뜨고 끝나면 읽는 화면으로 되끌려 오던」 길은
//   이 시험에서 생기지 않는다(수정을 되돌려도 통과했다). 이 시험은 질문이 있는 흐름이 읽는 화면 → 확인 화면 한 번으로 끝나는지만 지킨다. 되끌림을 막는 코드는 `plan-check.tsx` 의 `onReading`.
test("질문이 붙은 계획을 보내면 읽는 화면이 질문과 함께 그대로 있다가 확인 화면으로 한 번만 간다(확인 화면에서 읽는 화면으로 되끌려 오지 않는다)", async ({ page }) => {
  test.setTimeout(150_000);
  await start(page);
  await openRegistration(page);
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await checkPlan(page);
  await page.waitForURL(/\/intakes\/[^/]+$/, { timeout: 30_000 });
  await watch(page, 16_000);
  await page.waitForTimeout(16_500);
  const log = await screens(page);
  expect(log.length).toBeGreaterThan(0);
  expect(log[0]).toContain("읽는 화면");                                                                // 처음은 읽는 화면(질문이 있다)
  expect(backToReading(log)).toBe(0);                                                                  // 확인 화면이 한 번 뜬 뒤에는 읽는 화면으로 돌아가지 않는다
  expect(log.at(-1)).toContain("확인 화면(done)");
});

test("이미 읽은 계획을 뒤로 · 앞으로로 다시 열면 읽는 화면이 5초 뜨지 않고 곧장 확인 화면이며, 한 번 열린 뒤에는 다시 읽는 화면이 되지 않는다", async ({ page }) => {
  test.setTimeout(150_000);
  await start(page);
  await openRegistration(page);
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await checkPlan(page);
  await page.waitForURL(/\/intakes\/[^/]+$/, { timeout: 30_000 });
  await expect(page.getByRole("button", { name: "여행 등록" })).toBeVisible({ timeout: 60_000 });
  await page.goBack();
  await page.waitForURL(/\/trips\/new/);
  await page.goForward();
  await watch(page, 8_000);
  await page.waitForTimeout(8_500);
  const log = await screens(page);
  expect(log.some((entry) => entry.includes("읽는 화면"))).toBe(false);                                // 읽는 화면이 한 순간도 없다
  expect(log.every((entry) => entry.includes("확인 화면"))).toBe(true);
});
