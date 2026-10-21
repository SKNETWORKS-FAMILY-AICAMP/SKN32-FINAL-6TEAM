import { expect, test } from "@playwright/test";
import { checkPlan, mockServer, noHorizontalScroll, start } from "./helpers";
import { useMapTiles } from "./capture-map-tiles";
import { patchIntake } from "./plan-check-kit";

test.use({ video: "on" });

for (const width of [375, 1280]) {
  test(`첫 마커부터 전체 읽힌 목록이 접혀 있고 현재 검증 카드만 펼쳐진다 ${width}px`, async ({ page, request }) => {
    test.setTimeout(60000);
    await page.setViewportSize({ width, height: 812 });
    const api = mockServer(request);
    await api.reset();
    // `[2026-10-20 C안]` 확인이 필요한 일정이 있으면 첫 검사가 그 카드에서 멈춰 묻는다 — 재생 · 지도를 보는 이 시험은 고칠 것이 없는 판(`calm`)으로 끝까지 본다.
    await api.scenario({ questions: "none", readingPolls: 999, board: "calm", review: "on" });
    await useMapTiles(page);
    await start(page);
    const lines = ["10월 1일 서울 여행", "09:00 경복궁 관람", "11:00 올리브영", "12:30 광장시장"];
    await patchIntake(page, view => {
      for (const source of view.sources ?? []) {
        const read = source.lines[0]?.read ?? false;
        source.lines = lines.map((text, index) => ({ no: index + 1, text, read }));
        for (const item of source.items) item.line = item.index + 2;
      }
    });
    let release!: () => void;
    const ready = new Promise<void>(resolve => { release = resolve; });
    await page.route("**/v1/web/trip-intakes/*/events", async route => {
      const response = await route.fetch();
      await ready;
      await route.fulfill({ response });
    });
    await page.goto("/trips/new");
    await page.getByLabel("나의 여행 계획").fill(lines.join("\n"));
    await checkPlan(page);
    await expect(page.getByRole("heading", { name: "계획을 확인하고 있어요", exact: true })).toBeVisible();
    await api.scenario({ readingPolls: 0 });
    release();
    const checking = page.locator('[data-stage="checking"]');
    const first = page.locator('li[data-entry-id="0-0"]');
    const next = page.locator('li[data-entry-id="0-1"]');
    const last = page.locator('li[data-entry-id="0-2"]');
    const pins = page.locator('[aria-label="여행 지도"] [data-pin-body]');
    await expect(first).toHaveAttribute("data-reveal-current", "true", { timeout: 30000 });
    await expect(checking.locator('li[data-type="item"]')).toHaveCount(3);
    await expect(pins).toHaveCount(1);
    await expect(first.locator("[data-details]")).toHaveCount(1);
    for (const waiting of [next, last]) {
      await expect(waiting).toHaveAttribute("data-reveal-waiting", "true");
      await expect(waiting.locator("[data-details], [role=img], [data-card-footer-status]")).toHaveCount(0);
      await expect(waiting.locator("article")).toHaveAttribute("aria-busy", "false");
    }
    const geometry = await checking.evaluate(screen => {
      const current = screen.querySelector('[data-reveal-current="true"]')!.getBoundingClientRect();
      const future = screen.querySelector('[data-entry-id="0-1"]')!.getBoundingClientRect();
      const sheet = screen.querySelector('[class*="sheetBody"]')!;
      const bounds = sheet.getBoundingClientRect();
      return { currentY: current.y, futureY: future.y, top: bounds.top, bottom: bounds.bottom, scrollTop: sheet.scrollTop, scrollHeight: sheet.scrollHeight, height: sheet.clientHeight };
    });
    expect(geometry.currentY).toBeGreaterThanOrEqual(geometry.top - 2);
    expect(geometry.futureY).toBeLessThan(geometry.bottom);
    if (geometry.scrollHeight > geometry.height + 4) expect(geometry.scrollTop).toBeLessThan(geometry.scrollHeight - geometry.height);
    else expect(geometry.scrollTop).toBe(0);
    await test.info().attach("first-marker-list-geometry", { body: JSON.stringify(geometry), contentType: "application/json" });
    await page.screenshot({ path: test.info().outputPath(`first-marker-all-read-folded-${width}.png`) });
    await expect(next).toHaveAttribute("data-reveal-current", "true");
    await expect(first.locator("[data-details]")).toHaveCount(0);
    await expect(next.locator("[data-details]")).toHaveCount(1);
    await expect(last.locator("[data-details]")).toHaveCount(0);
    await expect(page.locator('[data-stage="done"]')).toBeVisible({ timeout: 20000 });
    await expect(page.locator('li[data-type="item"]')).toHaveCount(3);
    await expect(pins).toHaveCount(3);
    // 검증 후 기존 원형 일정 추가 동작을 그대로 제공해야 합니다.
    await expect(page.getByRole("button", { name: /일정 추가/ }).first()).toBeVisible();
    await noHorizontalScroll(page);
  });
}
