import { expect, test } from "@playwright/test";
import { mockServer } from "./helpers";
import { card, head, openFinished, toast } from "./plan-check-kit";
import { useMapTiles } from "./capture-map-tiles";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

for (const width of [375, 1280]) {
  test(`${width}px: 확인 필요와 되돌리기는 카드 하단 한 자리에서 교대로 표시된다`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    const tiles = process.env.CARD_EXCLUSIVE_SHOTS ? await useMapTiles(page) : async () => {};
    const server = await openFinished(page, request, undefined, { intakeEvents: "off" });
    await tiles();
    const intro = toast(page, "계획 확인 화면이에요");
    if (await intro.count()) await intro.getByRole("button", { name: "닫기", exact: true }).click();
    const item = card(page, "올리브영");
    const slot = item.locator("[data-card-footer-status]");
    const warning = item.getByText("확인 필요", { exact: true });
    const undo = item.getByRole("button", { name: "올리브영 시간 되돌리기", exact: true });
    const lowerRight = async () => {
      const box = (await item.boundingBox())!;
      const label = (await slot.boundingBox())!;
      const heading = (await item.getByRole("heading").boundingBox())!;
      expect(label.y).toBeGreaterThanOrEqual(heading.y + heading.height);
      expect(box.x + box.width - label.x - label.width).toBeLessThan(16);
      expect(box.y + box.height - label.y - label.height).toBeLessThan(16);
      await expect(item.locator('[class*=cardTools] [data-state="review"]')).toHaveCount(0);
      await expect(slot.locator(":scope > *")).toHaveCount(1);
    };
    await expect(warning).toBeVisible();
    await expect(undo).toHaveCount(0);
    await warning.scrollIntoViewIfNeeded();
    await lowerRight();
    await page.mouse.move(0, 0);
    if (process.env.CARD_EXCLUSIVE_SHOTS) await page.screenshot({ path: `${process.env.CARD_EXCLUSIVE_SHOTS}/review-${width}.png`, fullPage: true });
    await head(page, "올리브영").click();
    await expect(head(page, "올리브영")).toHaveAttribute("aria-expanded", "true");
    await lowerRight();
    await page.getByRole("button", { name: /^올리브영 시간 고치기/ }).click();
    const form = page.getByRole("form", { name: "올리브영 시간 고치기" });
    const together = form.getByLabel("앞뒤 일정도 함께 밀기");
    if (await together.count()) await together.uncheck();
    await form.getByLabel("끝", { exact: true }).fill("12:05");
    await form.getByRole("button", { name: "적용", exact: true }).click();
    await expect(undo).toBeVisible();
    await expect(warning).toHaveCount(0);
    await undo.scrollIntoViewIfNeeded();
    await lowerRight();
    const notice = toast(page, "1개 일정의 시간을 바꿨어요");
    await notice.getByRole("button", { name: "닫기", exact: true }).click();
    await page.mouse.move(0, 0);
    await page.waitForTimeout(250);
    if (process.env.CARD_EXCLUSIVE_SHOTS) await page.screenshot({ path: `${process.env.CARD_EXCLUSIVE_SHOTS}/undo-${width}.png`, fullPage: true });
    await undo.focus();
    await undo.press("Enter");
    await expect(undo).toHaveCount(0);
    await expect(warning).toBeVisible();
    await lowerRight();
    const edits = await server.received("POST", "/edits");
    expect(edits.at(-1)!.body!.edits).toContainEqual({ source_id: "s1", field: "items[1].ends_at", value: "12:00" });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
