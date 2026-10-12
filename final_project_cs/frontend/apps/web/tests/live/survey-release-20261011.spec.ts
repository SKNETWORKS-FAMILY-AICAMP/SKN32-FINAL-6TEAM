import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { checkPlan, mockServer, noHorizontalScroll, start } from "./helpers";

const result = (page: Page) => page.getByRole("button", { name: /^확인 필요 \d+곳$/ });
const questions = (page: Page) => page.getByRole("region", { name: "질문 2개" });

async function completedQuestions(page: Page, request: APIRequestContext, touched = false) {
  const server = mockServer(request);
  await server.reset();
  await server.scenario({ questions: "two", readingPolls: 999, board: "rich", review: "on" });
  await start(page);
  let release!: () => void;
  const ready = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/v1/web/trip-intakes/*/events", async (route) => {
    const response = await route.fetch();
    await ready;
    await route.fulfill({ response });
  });
  await page.goto("/trips/new");
  await page.clock.install();
  await page.getByLabel("나의 여행 계획").fill("10/15 09:00 경복궁 관람");
  await checkPlan(page);
  await expect(questions(page)).toBeVisible();
  if (touched) {
    await questions(page).getByRole("button", { name: "택시", exact: true }).click();
    await expect(questions(page)).toContainText("2 / 2");
  }
  await server.scenario({ readingPolls: 0 });
  release();
  await expect(page.getByRole("progressbar", { name: "계획 확인 진행" })).toHaveAttribute("aria-valuenow", "100");
  // Observe committed DOM changes, including the first frame after the hold is released.
  await page.evaluate(() => {
    const stages: string[] = [];
    const counts: number[] = [];
    const pins: number[] = [];
    Object.assign(window, { __releasedStages: stages, __releasedCounts: counts, __releasedPins: pins });
    const sample = () => {
      const screen = document.querySelector('[data-replay="playing"][data-stage]');
      if (screen) {
        stages.push(screen.getAttribute("data-stage")!);
        counts.push(screen.querySelectorAll('li[data-type="item"]').length);
        pins.push(screen.querySelectorAll('.leaflet-marker-icon[title]').length);
      }
    };
    new MutationObserver(sample).observe(document.body, { attributes: true, childList: true, subtree: true });
  });
}

async function completedResult(page: Page) {
  await expect(page.locator('[data-replay="playing"]')).toHaveAttribute("data-stage", "checking");
  // Let React commit each timer's update between virtual seconds.
  for (let second = 0; second < 50; second += 1) {
    await page.clock.runFor(1000);
    await page.waitForTimeout(20);
    if (await page.locator('[data-replay="playing"]').getAttribute("data-stage") === "done") break;
  }
  await expect(result(page)).toBeVisible({ timeout: 2000 });
  await expect(page.locator('[data-replay="playing"]')).toHaveAttribute("data-stage", "done");
  await expect(page.getByRole("heading", { name: "계획을 확인하고 있어요", exact: true })).toHaveCount(0);
  const stages = await page.evaluate(() => (window as unknown as { __releasedStages: string[] }).__releasedStages);
  expect(stages.length).toBeGreaterThan(0);
  expect(stages.every((stage) => stage === "checking" || stage === "done"), stages.join(" → ")).toBe(true);
  expect(stages).toContain("checking");
  const counts = await page.evaluate(() => (window as unknown as { __releasedCounts: number[] }).__releasedCounts);
  // The completed reading keeps every known title in the folded list.
  // Checking reveals checks/map pins, rather than deleting the known titles.
  expect(counts.length).toBeGreaterThan(0);
  expect(counts.every((count) => count === 3)).toBe(true);
  await expect(page.locator('li[data-type="item"]')).toHaveCount(3);
  const pins = await page.evaluate(() => (window as unknown as { __releasedPins: number[] }).__releasedPins);
  expect(pins.some((count) => count > 0 && count < 3)).toBe(true);
  expect(pins).toContain(3);
  await noHorizontalScroll(page);
}

for (const width of [375, 1280]) {
  test.describe(`${width}px 질문 완료 이동`, () => {
    test.use({ viewport: { width, height: 812 } });
    test("수동 확인은 읽기를 재생하지 않고 지도 일정을 순차 표시한다", async ({ page, request }) => {
      await completedQuestions(page, request);
      await page.getByRole("button", { name: "읽어 온 계획 확인하기", exact: true }).click();
      await completedResult(page);
      if (process.env.SURVEY_RELEASE_SHOTS) await page.screenshot({ path: `${process.env.SURVEY_RELEASE_SHOTS}/result-${width}.png`, fullPage: true, animations: "disabled" });
    });
    test("5초 자동 이동도 지도 일정을 순차 표시한다", async ({ page, request }) => {
      await completedQuestions(page, request);
      await page.clock.fastForward(5100);
      await completedResult(page);
    });
    test("무응답 경고가 끝나도 완료 결과를 재재생하지 않는다", async ({ page, request }) => {
      await completedQuestions(page, request, true);
      await page.clock.fastForward(30100);
      await expect(page.getByRole("alertdialog")).toBeVisible();
      await page.clock.runFor(21000);
      await completedResult(page);
    });
    for (const exit of ["button", "escape"] as const) {
      test(`계속 답하기 ${exit === "button" ? "버튼" : "Esc"}는 자동 넘김을 멈추고 질문·초점을 유지한다`, async ({ page, request }) => {
        await completedQuestions(page, request, true);
        const heading = questions(page).getByRole("heading");
        await heading.focus();
        await page.clock.fastForward(30100);
        const warning = page.getByRole("alertdialog");
        await expect(warning).toBeVisible();
        await expect(warning.getByRole("button")).toHaveCount(1);
        const keep = warning.getByRole("button", { name: "계속 답하기", exact: true });
        await expect(keep).toBeFocused();
        await page.keyboard.press("Tab");
        await expect(keep).toBeFocused();
        await page.keyboard.press("Shift+Tab");
        await expect(keep).toBeFocused();
        if (exit === "button" && process.env.SURVEY_RELEASE_SHOTS) {
          await page.screenshot({ path: `${process.env.SURVEY_RELEASE_SHOTS}/idle-${width}.png`, fullPage: true, animations: "disabled" });
        }
        if (exit === "button") await keep.click();
        else await page.keyboard.press("Escape");
        await expect(warning).toHaveCount(0);
        await expect(heading).toBeFocused();
        // Leave wall-clock time for background API responses between virtual seconds.
        // Advancing a whole minute at once can abort an unrelated notice refresh before its mock response arrives.
        for (let second = 0; second < 61; second += 1) {
          await page.clock.runFor(1000);
          await page.waitForTimeout(20);
        }
        await expect(warning).toHaveCount(0);
        await expect(questions(page)).toBeVisible();
        await expect(questions(page)).toContainText("2 / 2");
        await questions(page).getByRole("button", { name: "이전 질문 보기" }).click();
        await expect(questions(page).getByRole("button", { name: "택시", exact: true })).toHaveAttribute("aria-pressed", "true");
        await page.getByRole("button", { name: "읽어 온 계획 확인하기", exact: true }).click();
        await completedResult(page);
      });
    }
  });
}
