import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { dayTab, mockServer, noHorizontalScroll, start, TRIP_ID, tripScreen } from "./helpers";
import { mapSettled } from "./plan-check-kit";

test.beforeEach(async ({ page, request }) => { await mockServer(request).reset(); await mockServer(request).scenario({ routeShapes: "on" }); await start(page); });

for (const width of [375, 1280]) for (const reduced of [false, true]) {
  test(`${width}px ${reduced ? "동작 줄임" : "일반"}: 예약 있는 일정만 표시하고 검증 화면의 선택 시각·경로를 유지한다`, async ({ page }) => {
    await page.setViewportSize({ width, height: 812 });
    await page.emulateMedia({ reducedMotion: reduced ? "reduce" : "no-preference" });
    await page.goto(`/trips/${TRIP_ID}`);
    await expect(tripScreen(page)).toBeVisible();
    await mapSettled(page);
    const first = page.locator('[data-entry-id="i-a"]');
    const booked = page.locator('[data-entry-id="i-b"]');
    await expect(first).not.toContainText("예약 정보 없음");
    await expect(first.locator("[data-booked]")).toHaveCount(0);
    await expect(booked.locator("[data-booked]")).toHaveText("예약 있음");
    await expect(first.locator("[data-stop-start]")).toHaveCSS("font-size", "16px");
    await expect(first.locator("[data-stop-start]")).toHaveCSS("font-weight", "400");
    await expect(first.locator("[data-stop-end]")).toHaveCSS("opacity", "0");
    await expect(page.locator("path.trip-route-line")).toHaveCount(2);
    await expect(page.locator("path.trip-route-line--dashed")).toHaveCount(1);
    await page.locator("#stop-button-i-a").click();
    await expect(first.locator("[data-stop-end]")).toHaveText("~09:00");
    await expect(first.locator("[data-stop-end]")).toHaveCSS("opacity", "1");
    await expect(first.locator("[data-stop-start]")).toHaveCSS("font-weight", "600");
    await expect(first.locator("[data-stop-end]")).toHaveCSS("font-size", "12px");
    await expect(first.locator("[data-stop-end]")).toHaveCSS("font-weight", "400");
    if (reduced) expect(await first.locator("[data-stop-end]").evaluate((el) => parseFloat(getComputedStyle(el).transitionDuration))).toBeLessThanOrEqual(0.001);
    await noHorizontalScroll(page);
    await mkdir("mockups/registered-trip-parity-2026-10-11-v1", { recursive: true });
    await page.mouse.move(0, 0);
    await page.screenshot({ path: `mockups/registered-trip-parity-2026-10-11-v1/${width}-${reduced ? "reduce" : "normal"}.png` });
    await page.locator("#stop-button-i-b").click();
    await expect(first.locator("[data-stop-end]")).toHaveCSS("opacity", "0");
    await page.getByRole("button", { name: "경복궁 관람 상세 보기", exact: true }).click();
    await expect(page.locator("#main-content")).not.toContainText("예약 정보 없음");
    await expect(page.locator('[data-booked]')).not.toHaveCount(0);
    await page.getByRole("button", { name: "상세 보기 닫기", exact: true }).click();
    const move = page.locator('[data-entry-id="i-m"]');
    await expect(move.locator("[data-move-departure]")).toHaveText("11:10");
    await expect(move.locator("[data-move-arrival]")).toHaveCSS("opacity", "0");
    await move.getByRole("button", { name: /도보/ }).click();
    await expect(move.locator("[data-move-arrival]")).toHaveText("~11:30");
    await expect(move.locator("[data-move-arrival]")).toHaveCSS("opacity", "1");
    await dayTab(page, /^2일차/).click();
    await expect(page.locator("path.trip-route-line")).toHaveCount(0);
  });
}
