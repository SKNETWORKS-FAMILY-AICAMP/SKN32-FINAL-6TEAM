import { expect, test } from "@playwright/test";
import { checkPlan, fillPlanAsk, mockServer, openRegistration, start, weekAhead } from "./helpers";

/**
 * `[2026-10-28 사용자 결정]` 계획 읽기 · 계획 짜기 화면의 예상 안내는 「2분쯤 걸릴 수 있어요」다 — 옛 「1분쯤 걸려요」를 바꿨다(새 안내를 덧붙이지 않는다).
 * ★테스트용 모방 서버 시험이다. 문구만 본다 — 시간 제한 · 실제 속도는 바꾸지 않았고, 이 시험이 실제 서버 시간을 재지 않는다.
 */
const INTAKE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const english = () => localStorage.setItem("tripilot.web.settings.v1", JSON.stringify({ language: "en" }));

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

for (const lang of ["ko", "en"] as const) {
  test(`읽는 중 화면(${lang})은 「2분쯤 걸릴 수 있어요」라고 하고 1분이라고 하지 않는다`, async ({ page, request }) => {
    await mockServer(request).scenario({ readingPolls: 99, intakeEvents: "off" });
    if (lang === "en") await page.addInitScript(english);
    await start(page);
    await page.goto(`/intakes/${INTAKE}`);
    const head = page.getByRole("heading", { name: lang === "ko" ? "계획을 확인하고 있어요" : "Checking your plan", level: 1 });
    await expect(head).toBeVisible();
    const desc = page.locator("header").filter({ has: head }).locator("p").first();
    await expect(desc).toHaveText(lang === "ko" ? "사진 한 장은 2분쯤 걸릴 수 있어요. 이 화면을 열어 두면 끝나는 대로 보여 드려요."
      : "A photo can take about two minutes. Keep this page open and the result will appear.");
    await expect(page.getByText(/1분쯤|about a minute/)).toHaveCount(0);
  });

  test(`일정을 짜는 중 화면(${lang})은 「2분쯤 걸릴 수 있어요」라고 하고 1분이라고 하지 않는다`, async ({ page, request }) => {
    await mockServer(request).scenario({ readingPolls: 0, planDelay: 3000 });
    if (lang === "en") await page.addInitScript(english);
    await start(page);
    await openRegistration(page);
    if (lang === "ko") {
      await fillPlanAsk(page, { start: weekAhead(), days: 2, party: 2 });
      await checkPlan(page);
    } else {
      // `fillPlanAsk` · `checkPlan` find the Korean labels; the English page is filled by the same fields' ids and the English button names.
      await page.locator("#plan-start").fill(weekAhead());
      await page.locator("#plan-days").selectOption("2");
      await page.locator("#plan-party").selectOption("2");
      await page.getByRole("button", { name: "Check my plan" }).click();
      const card = page.getByRole("dialog");
      if (await card.waitFor({ state: "visible", timeout: 2500 }).then(() => true, () => false)) await card.getByRole("button", { name: "Turn on and go on" }).click();
    }
    await expect(page).toHaveURL(/\/intakes\/starting$/);
    await expect(page.getByText(lang === "ko" ? "조건에 맞는 일정을 짜서 확인하고, 통과하면 바로 여행으로 등록해요. 2분쯤 걸릴 수 있어요."
      : "We plan the days, check them and register the trip right away. It can take about two minutes.")).toBeVisible();
    await expect(page.getByText(/1분쯤|about a minute/)).toHaveCount(0);
  });
}
