import { expect, test } from "@playwright/test";
import { mkdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { mockServer } from "./helpers";
import { openFinished } from "./plan-check-kit";
import { allowLocation, startWithLocationConsent } from "./location-kit";

/** Native Chrome captures, cached map tiles and a prepared browser location. No external tile requests. */
for (const scene of [{ width: 375, located: false }, { width: 1280, located: false }, { width: 375, located: true }]) test(`촬영 ${scene.width}px ${scene.located ? "내 위치" : "왼쪽 도구"}`, async ({ page, context, request }) => {
  test.skip(!process.env.LOCATION_TILE_CACHE, "촬영용으로 저장된 지도 타일 폴더를 지정해야 합니다.");
  await page.setViewportSize({ width: scene.width, height: 900 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  const missing: string[] = [];
  let pending = 0;
  await page.route("**/__test/tile/**", async route => {
    pending += 1;
    const name = new URL(route.request().url()).pathname.split("/__test/tile/")[1].replaceAll("/", "_");
    try { await route.fulfill({ contentType: "image/png", body: await readFile(join(process.env.LOCATION_TILE_CACHE!, name)) }); }
    catch { missing.push(name); await route.abort(); }
    finally { pending -= 1; }
  });
  await mockServer(request).reset();
  if (scene.located) {
    await startWithLocationConsent(page, true);
    await allowLocation(context, { latitude: 37.5796, longitude: 126.977, accuracy: 25 });
  }
  await openFinished(page, request);
  await expect(page.getByRole("status").filter({ hasText: "계획 확인 화면이에요" })).toHaveCount(0);
  await page.getByRole("button", { name: "목록 높이 바꾸기" }).focus();
  for (let press = 0; press < 5; press += 1) await page.keyboard.press("ArrowUp");
  const group = page.getByRole("group", { name: "지도 단추" });
  await group.getByRole("button", { name: "지도 단추 펼치기" }).click();
  await expect(group).toHaveAttribute("data-layout", "row");
  if (scene.located) { await group.getByRole("button", { name: "내 위치로", exact: true }).click(); await expect(page.getByRole("img", { name: "내 위치", exact: true })).toBeInViewport(); }
  await expect(page.getByRole("region", { name: "여행 지도" })).not.toHaveAttribute("data-moving");
  await expect.poll(() => pending).toBe(0);
  expect(missing).toEqual([]);
  await expect(page.locator(".leaflet-tile-loaded").first()).toBeVisible();
  await group.hover();
  await page.waitForTimeout(1_800); // Capture the settled map and restored date tabs.
  await page.mouse.move(0, 0);
  await mkdir("mockups/location-entry-2026-10-11-v4", { recursive: true });
  await page.screenshot({ path: `mockups/location-entry-2026-10-11-v4/${scene.located ? "located" : "tools"}-${scene.width}.png` });
  if (!scene.located) {
    await group.getByRole("button", { name: "내 위치로", exact: true }).click();
    await expect(page.getByRole("dialog", { name: "내 위치로 이동" })).toBeVisible();
    await page.screenshot({ path: `mockups/location-entry-2026-10-11-v4/consent-${scene.width}.png` });
  }
});
