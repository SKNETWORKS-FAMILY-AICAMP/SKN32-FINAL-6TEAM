import { expect, test } from "@playwright/test";
import { checkPlan, mockServer, noHorizontalScroll, start } from "./helpers";

test.use({ video: { mode: "on", size: { width: 1280, height: 812 } } });

for (const width of [375, 1280]) {
  test.describe(`${width}px 실제 시간의 첫 지도 표시`, () => {
    test.use({ viewport: { width, height: 812 } });
    test("질문 뒤 일정과 마커가 하나씩 등장하고 읽기 화면은 되돌아오지 않는다", async ({ page, request }) => {
      const api = mockServer(request);
      await api.reset();
      await api.scenario({ questions: "two", readingPolls: 999, board: "rich", review: "on" });
      await start(page);
      let release!: () => void;
      const ready = new Promise<void>((resolve) => { release = resolve; });
      await page.route("**/v1/web/trip-intakes/*/events", async (route) => {
        const response = await route.fetch();
        await ready;
        await route.fulfill({ response });
      });
      await page.goto("/trips/new");
      await page.getByLabel("나의 여행 계획").fill("10/15 09:00 경복궁 관람");
      await checkPlan(page);
      await expect(page.getByRole("region", { name: "질문 2개" })).toBeVisible();
      await api.scenario({ readingPolls: 0 });
      release();
      await expect(page.getByRole("progressbar", { name: "계획 확인 진행" })).toHaveAttribute("aria-valuenow", "100");
      await page.evaluate(() => {
        const frames: { at: number; stage: string; count: number; pins: number }[] = [];
        Object.assign(window, { __firstMapFrames: frames });
        const sample = () => {
          const screen = document.querySelector('[data-replay="playing"][data-stage]');
          if (screen) frames.push({ at: performance.now(), stage: screen.getAttribute("data-stage")!, count: screen.querySelectorAll('li[data-type="item"]').length, pins: screen.querySelectorAll("[data-pin-body]").length });
          if (!frames.some((frame) => frame.stage === "done")) requestAnimationFrame(sample);
        };
        requestAnimationFrame(sample);
      });
      await page.getByRole("button", { name: "읽어 온 계획 확인하기", exact: true }).click();
      await expect(page.locator('[data-replay="playing"]')).toHaveAttribute("data-stage", "checking");
      await expect(page.getByRole("progressbar", { name: "계획 확인 진행" })).toHaveAttribute("aria-valuenow", "100");
      await expect(page.getByRole("progressbar", { name: "계획 확인 진행" })).toContainText("정리 완료");
      await expect(page.locator('li[data-type="item"]')).toHaveCount(1);
      await page.screenshot({ path: test.info().outputPath(`first-map-one-${width}.png`), animations: "disabled" });
      await expect(page.locator('[data-replay="playing"]')).toHaveAttribute("data-stage", "done", { timeout: 20000 });
      await expect(page.getByRole("heading", { name: "계획을 확인하고 있어요", exact: true })).toHaveCount(0);
      const frames = await page.evaluate(() => (window as unknown as { __firstMapFrames: { at: number; stage: string; count: number; pins: number }[] }).__firstMapFrames);
      await test.info().attach("actual-frame-counts", { body: JSON.stringify(frames), contentType: "application/json" });
      expect(frames.every((frame) => frame.stage === "checking" || frame.stage === "done")).toBe(true);
      const counts = frames.map((frame) => frame.count);
      expect(counts).toContain(1); expect(counts).toContain(2); expect(counts).toContain(3);
      expect(frames.find((frame) => frame.count === 3)!.at - frames.find((frame) => frame.count === 1)!.at).toBeGreaterThanOrEqual(600);
      expect(frames.some((frame) => frame.pins === 1)).toBe(true);
      expect(frames.some((frame) => frame.pins === 2)).toBe(true);
      await page.screenshot({ path: test.info().outputPath(`first-map-done-${width}.png`), animations: "disabled" });
      await noHorizontalScroll(page);
    });
  });
}
