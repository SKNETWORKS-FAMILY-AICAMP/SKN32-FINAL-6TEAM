import { expect, test } from "@playwright/test";
import { mockServer, noHorizontalScroll } from "./helpers";
import { card, head, openFinished } from "./plan-check-kit";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

for (const width of [375, 1280]) {
  for (const crowded of [false, true]) {
    test(`${width}px ${crowded ? "문제가 많으면 줄을 바꾸고 상태는 아래 오른쪽" : "문제 항목은 확인 필요 바로 왼쪽"}`, async ({ page, request }) => {
      await page.setViewportSize({ width, height: 812 });
      await openFinished(page, request, crowded ? (view) => {
        const item = view.review.items.find((entry: { title: string }) => entry.title === "올리브영");
        item.rows = ["place", "time", "hours", "closed", "booking", "route", "mode", "arrival"].map((row) => ({ row, result: "warn", text: "방문 전에 확인해 주세요" }));
      } : undefined, { intakeEvents: "off" });
      const target = card(page, "올리브영");
      await target.scrollIntoViewIfNeeded();
      const needs = target.locator('[class*="needsInline"]');
      const status = target.locator('[data-card-footer-status] [data-state="review"]');
      await expect(needs).toBeVisible();
      await expect(status).toBeVisible();
      const box = (await target.boundingBox())!;
      const noteBox = (await needs.boundingBox())!;
      const stateBox = (await status.boundingBox())!;
      expect(Math.abs(box.x + box.width - stateBox.x - stateBox.width - 13)).toBeLessThanOrEqual(2);
      if (!crowded) {
        expect(Math.abs(stateBox.x - noteBox.x - noteBox.width - 12)).toBeLessThanOrEqual(2);
        expect(Math.abs(stateBox.y + stateBox.height - noteBox.y - noteBox.height)).toBeLessThanOrEqual(2);
      } else {
        await expect(needs.locator(':scope > span')).toHaveCount(8);
        expect(stateBox.y + stateBox.height).toBeGreaterThanOrEqual(noteBox.y + noteBox.height - 1);
        for (const need of await needs.locator(':scope > span').all()) {
          const needBox = (await need.boundingBox())!;
          expect(needBox.x).toBeGreaterThanOrEqual(box.x);
          expect(needBox.x + needBox.width).toBeLessThanOrEqual(box.x + box.width);
        }
      }
      await noHorizontalScroll(page);
      await target.screenshot({ path: test.info().outputPath(`card-status-${crowded ? "wrap" : "group"}-${width}.png`), animations: "disabled" });
      await head(page, "올리브영").click();
      await expect(target.locator('[id$="-checks"][data-details]')).toBeVisible();          // `[2026-10-21]` 결과 화면 질문 칸도 data-details 를 단다
      await expect(target.locator('[class*="needsInline"]')).toHaveCount(0);
      await expect(status).toBeVisible();
    });
  }
}
