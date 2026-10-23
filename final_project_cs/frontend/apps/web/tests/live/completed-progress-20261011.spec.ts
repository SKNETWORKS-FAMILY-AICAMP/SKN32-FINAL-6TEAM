import { expect, test } from "@playwright/test";
import { checkPlan, mockServer, noHorizontalScroll, start } from "./helpers";

for (const width of [375, 1280]) {
  test.describe(`${width}px 완료 상태`, () => {
    test.use({ viewport: { width, height: 812 } });
    test("질문이 남아 완료 화면을 붙잡아도 마지막 7/8 진행 문구는 사라지고 결과 화면에서도 되살아나지 않는다", async ({ page, request }) => {
      const server = mockServer(request);
      await server.reset();
      // `[2026-10-20 C안]` 확인이 필요한 일정이 있으면 첫 검사가 그 카드에서 멈춰 묻는다 — 재생 · 지도를 보는 이 시험은 고칠 것이 없는 판(`calm`)으로 끝까지 본다.
      await server.scenario({ questions: "two", readingPolls: 999, board: "calm", review: "on" });
      await start(page);
      // 실제 SSE 응답의 마지막 진행 값만 7/8로 바꾼다. 완료 이벤트와 결과 조회는 기존 mock 서버가 보낸다.
      let injected = false;
      let release!: () => void;
      const ready = new Promise<void>((resolve) => { release = resolve; });
      await page.route("**/v1/web/trip-intakes/*/events", async (route) => {
        const response = await route.fetch();
        const chunks = (await response.text()).split("\n\n");
        const indexes = chunks.flatMap((chunk, index) => chunk.startsWith("event: progress\n") ? [index] : []);
        const last = indexes.at(-1);
        if (last !== undefined) {
          const packet = JSON.parse(chunks[last].split("data: ")[1]);
          chunks[last] = `event: progress\ndata: ${JSON.stringify({ ...packet, phase: "moves", done: 7, total: 8, current: { id: "last-move", title: "인사동 → 창덕궁" } })}`;
          injected = true;
        }
        await ready;
        await route.fulfill({ response, body: chunks.join("\n\n") });
      });
      await page.goto("/trips/new");
      await page.getByLabel("나의 여행 계획").fill("10/15 09:00 경복궁 관람");
      await checkPlan(page);
      await expect(page.getByRole("region", { name: "질문 2개" })).toBeVisible();
      await server.scenario({ readingPolls: 0 });
      release();
      await expect(page.getByText("계획을 다 읽었어요", { exact: true }).first()).toBeVisible();
      expect(injected).toBe(true);
      const bar = page.getByRole("progressbar", { name: "계획 확인 진행" });
      await expect(bar).toHaveAttribute("aria-valuenow", "100");
      await expect(bar).toHaveAttribute("aria-valuetext", "정리 완료 · 100%");
      await expect(bar).not.toContainText("7/8");
      await expect(bar).not.toContainText("이동 확인 중");
      await page.getByRole("button", { name: "자동으로 넘어가지 않기" }).click();
      await noHorizontalScroll(page);
      if (process.env.COMPLETED_SHOTS) {
        await page.locator('#main-content > div').filter({ has: page.getByRole('heading', { name: '계획을 확인하고 있어요', exact: true }) }).evaluate((element) => element.scrollTo({ top: 0, behavior: "instant" }));
        await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
        await page.screenshot({ path: `${process.env.COMPLETED_SHOTS}/completed-questions-${width}.png`, fullPage: true });
      }
      await page.getByRole("button", { name: "읽어 온 계획 확인하기", exact: true }).click();
      await expect(page.getByRole("heading", { name: "계획을 확인하고 있어요", exact: true })).toHaveCount(0);
      await expect(page.locator('main[data-stage="done"]')).toBeVisible({ timeout: 20000 });
      await expect(page.getByText("7/8 · 인사동 → 창덕궁 이동 확인 중", { exact: true })).toHaveCount(0);
    });
  });
}
