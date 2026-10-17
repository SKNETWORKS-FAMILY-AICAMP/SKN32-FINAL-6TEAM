import { expect, test } from "@playwright/test";
import { galleryShot, mockServer, noHorizontalScroll } from "./helpers";
import { openFinished } from "./plan-check-kit";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });
const gallery = "mockups/submit-at-list-end-2026-10-11-v1";

for (const width of [375, 1280]) for (const reduced of [false, true]) {
  test(`${width}px ${reduced ? "동작 줄임" : "일반 동작"}: 목록 끝에서 스크롤 중에도 제출 표시`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    await page.emulateMedia({ reducedMotion: reduced ? "reduce" : "no-preference" });
    const server = await openFinished(page, request, undefined, { intakeEvents: "off" });
    const body = page.locator("div[class*=sheetBody]");
    const footer = page.locator("footer[class*=footer]");
    await body.evaluate(element => { element.scrollTop = (element.scrollHeight - element.clientHeight) / 2; });
    await expect(footer).toHaveAttribute("data-quiet");
    await body.hover();
    await page.mouse.wheel(0, 10000);
    await expect.poll(() => body.evaluate(element => element.scrollHeight - element.clientHeight - element.scrollTop)).toBeLessThanOrEqual(2);
    // This must precede the existing 800ms idle restoration.
    await expect(footer).not.toHaveAttribute("data-quiet", { timeout: 250 });
    await expect(footer).not.toHaveAttribute("inert");
    await expect(footer).toHaveCSS("opacity", "1");
    await page.mouse.wheel(0, 150);
    await expect(footer).not.toHaveAttribute("data-quiet", { timeout: 250 });
    if (reduced) await expect(footer).toHaveCSS("transform", "none");
    await noHorizontalScroll(page);
    await page.mouse.move(0, 0);
    await galleryShot(page, `${gallery}/bottom-${width}-${reduced ? "reduce" : "normal"}.png`);
    const action = footer.getByRole("button", { name: "다시 제출", exact: true });
    await action.focus();
    await expect(action).toBeFocused();
    await page.getByRole("button", { name: "메뉴", exact: true }).focus();
    await body.hover();
    await page.mouse.wheel(0, -100);
    await expect(footer).toHaveAttribute("data-quiet", "true", { timeout: 250 });
    expect(await server.received("POST", "/revalidate")).toHaveLength(0);
    expect(await server.received("POST", "/confirm")).toHaveLength(0);
  });
}

test("목록 끝에서 접어도 제출은 숨고 다시 펼치면 복귀한다", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await openFinished(page, request, undefined, { intakeEvents: "off" });
  const body = page.locator("div[class*=sheetBody]");
  const footer = page.locator("footer[class*=footer]");
  await body.evaluate(element => { element.scrollTop = element.scrollHeight; });
  await expect(footer).not.toHaveAttribute("data-quiet", { timeout: 250 });
  const handle = page.getByRole("button", { name: "목록 높이 바꾸기" });
  await handle.click();
  await handle.click();
  await expect(page.locator("[data-collapsed]")).toHaveCount(1);
  await expect(footer).toHaveAttribute("data-quiet");
  await expect(footer).toHaveAttribute("inert");
  await handle.click();
  await expect(footer).not.toHaveAttribute("data-quiet");
});
