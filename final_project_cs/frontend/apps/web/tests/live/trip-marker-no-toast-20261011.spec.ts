import { expect, test } from "@playwright/test";
import { beforeTheTrip, galleryShot, mockServer, start, TRIP_ID, tripScreen } from "./helpers";
import { mapSettled } from "./plan-check-kit";

// `[2026-10-13]` 가짜 서버 여행(2026-10-01)이 「지난 일정」으로 그려지지 않게 여행 전날로 시계를 고정한다(helpers.ts beforeTheTrip).
test.beforeEach(async ({ page }) => { await beforeTheTrip(page); });
test.beforeEach(async ({ page, request }) => { await mockServer(request).reset(); await start(page); });
const pin = (page: import("@playwright/test").Page, name: string) => page.locator(`.leaflet-marker-icon[title^="${name}"]`);

for (const width of [375, 1280]) {
  test(`${width}px 마커 클릭·해제와 목록의 지도 보기는 안내 토스트를 띄우지 않는다`, async ({ page }) => {
    await page.setViewportSize({ width, height: 812 });
    await page.goto(`/trips/${TRIP_ID}`);
    await expect(tripScreen(page)).toBeVisible();
    await mapSettled(page);
    const first = pin(page, "1. 아침 식당");
    await first.locator("[data-pin-body]").click();
    await expect(page.locator('[data-entry-id="i-a"]')).toHaveAttribute("data-selected", "true");
    await expect(page.locator("#stop-button-i-a")).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByRole("status")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "목록에서 보기", exact: true })).toHaveCount(0);
    await mapSettled(page);
    await page.mouse.move(0, 0);
    await galleryShot(page, `mockups/trip-marker-no-toast-2026-10-11-v1/selected-${width}.png`);
    await first.locator("[data-pin-body]").click();
    await expect(page.locator("#stop-button-i-a")).toHaveAttribute("aria-expanded", "false");
    await expect(page.getByRole("status")).toHaveCount(0);
    await page.locator("#stop-button-i-b").click();
    // `[2026-10-12 결정 E]` 「지도에서 보기」 단추는 「상세 보기」로 바뀌었다 — 일정을 펼치는 것만으로 핀이 선택되고 안내는 없다.
    await expect(page.locator('[data-entry-id="i-b"]')).toHaveAttribute("data-selected", "true");
    await expect(page.locator("#stop-button-i-b")).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByRole("status")).toHaveCount(0);
  });
}

test("실제 선택 요청 알림은 마커를 선택·해제해도 유지한다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ bell: "on" });
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(tripScreen(page)).toBeVisible();
  await mapSettled(page);
  await server.scenario({ proposals: "open" });
  await expect.poll(() => server.ring(["notice", "proposal"])).toBeGreaterThan(0);
  const notice = page.getByRole("status").filter({ hasText: "선택 요청" });
  await expect(notice).toBeVisible();
  const first = pin(page, "3. 점심 식당");
  await first.locator("[data-pin-body]").click();
  await expect(notice).toBeVisible();
  await mapSettled(page);
  await expect(page.locator("#stop-button-i-c")).toHaveAttribute("aria-expanded", "true");
  await first.dispatchEvent("click");
  await expect(page.locator("#stop-button-i-c")).toHaveAttribute("aria-expanded", "false");
  await expect(notice).toBeVisible();
  await expect(page.getByRole("button", { name: "목록에서 보기", exact: true })).toHaveCount(0);
});
