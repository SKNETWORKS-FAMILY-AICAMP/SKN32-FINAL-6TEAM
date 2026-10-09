import { expect, test } from "@playwright/test";
import { mockServer } from "./helpers";
import { openFinished } from "./plan-check-kit";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });
const stripOf = (page: import("@playwright/test").Page) => page.locator('[role="tablist"][aria-label="일차 고르기"]');
async function openDays(page: import("@playwright/test").Page, request: import("@playwright/test").APIRequestContext) {
  await page.setViewportSize({ width: 375, height: 812 });
  await openFinished(page, request, (view) => {
    view.review.items.push({ ...view.review.items[0], id: "0-3", index: 3, title: "N서울타워", day: 2, date: "2026-10-02" });
  });
  await expect(stripOf(page)).toHaveCSS("opacity", "1");
}
async function shot(page: import("@playwright/test").Page, name: string) {
  if (process.env.DAY_STRIP_SHOTS) await page.screenshot({ path: `${process.env.DAY_STRIP_SHOTS}/${name}.png`, fullPage: true });
}

test("목록을 스크롤하면 일차 줄만 사라지고 멈춘 뒤 다시 나타나며 목록 위치는 유지된다", async ({ page, request }) => {
  await openDays(page, request);
  await shot(page, "01-resting");
  const body = page.locator("div[class*=sheetBody]");
  await body.hover();
  await page.mouse.wheel(0, 130);
  await expect(stripOf(page)).toHaveCSS("opacity", "0");
  await expect(stripOf(page)).toHaveAttribute("inert", "");
  await shot(page, "02-scrolling-hidden");
  const at = await body.evaluate((element) => element.scrollTop);
  await expect(stripOf(page)).toHaveCSS("opacity", "1");
  expect(Math.abs(await body.evaluate((element) => element.scrollTop) - at)).toBeLessThan(3);
  await shot(page, "03-restored");
  await page.setViewportSize({ width: 1280, height: 720 });
  await shot(page, "04-desktop-restored");
});

test("지도를 누르고 움직이는 동안은 계속 숨고 손을 놓은 뒤 복귀한다", async ({ page, request }) => {
  await openDays(page, request);
  const map = (await page.getByRole("region", { name: "여행 지도" }).boundingBox())!;
  await page.mouse.move(map.x + 55, map.y + 140);
  await page.mouse.down();
  await page.mouse.move(map.x + 75, map.y + 160, { steps: 5 });
  await expect(stripOf(page)).toHaveCSS("opacity", "0");
  await page.waitForTimeout(1100);
  await expect(stripOf(page)).toHaveCSS("opacity", "0");
  await page.mouse.up();
  await expect(stripOf(page)).toHaveCSS("opacity", "1");
});

test("일차 버튼 조작은 숨기지 않고 숨은 중에도 Tab을 누르면 다시 접근할 수 있다", async ({ page, request }) => {
  await openDays(page, request);
  await page.getByRole("tab", { name: /^2일차/ }).click();
  await expect(stripOf(page)).toHaveCSS("opacity", "1");
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByRole("tab", { name: /^1일차/ })).toBeFocused();
  await expect(stripOf(page)).toHaveCSS("opacity", "1");
  await page.locator("div[class*=sheetBody]").hover();
  await page.mouse.wheel(0, 90);
  // A tab with keyboard focus stays visible, even if the mouse wheel is used.
  await expect(stripOf(page)).toHaveCSS("opacity", "1");
  await page.getByRole("button", { name: "메뉴", exact: true }).focus();
  await page.locator("div[class*=sheetBody]").hover();
  await page.mouse.wheel(0, 90);
  await expect(stripOf(page)).toHaveCSS("opacity", "0");
  await page.keyboard.press("Tab");
  await expect(stripOf(page)).not.toHaveAttribute("data-quiet", "true", { timeout: 300 });
  await expect(stripOf(page)).toHaveCSS("opacity", "1");
  await expect(stripOf(page)).not.toHaveAttribute("inert", "");
});

test("동작 줄이기 설정에서도 숨김·복귀가 되며 위치 이동 효과는 없다", async ({ page, request }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await openDays(page, request);
  await page.locator("div[class*=sheetBody]").hover();
  await page.mouse.wheel(0, 100);
  await expect(stripOf(page)).toHaveCSS("opacity", "0");
  await expect(stripOf(page)).toHaveCSS("transform", "none");
  await expect(stripOf(page)).toHaveCSS("opacity", "1");
});
