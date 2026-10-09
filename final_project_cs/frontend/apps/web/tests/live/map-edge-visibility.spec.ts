import { expect, test } from "@playwright/test";
import { mockServer } from "./helpers";
import { openFinished, pin } from "./plan-check-kit";

/** 실제 Leaflet 렌더링, 관광·계획·지도 타일은 mock 서버 응답. */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

for (const width of [375, 1280]) {
  test(`${width}px: 묶인 거리 칩의 모든 마커·연결선은 숨고 복귀 시 같은 마커가 살아난다`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 1000 });
    await openFinished(page, request);
    const map = page.getByRole("region", { name: "여행 지도", exact: true });
    const bodies = map.locator("[data-pin-body]");
    await expect(bodies).toHaveCount(3);
    await bodies.evaluateAll((nodes) => nodes.forEach((node, index) => { (node as HTMLElement).dataset.visibilityIdentity = String(index); }));
    const linesBefore = await map.locator(".trip-route-line").count();
    const area = (await map.boundingBox())!;
    for (let step = 0; step < 5; step += 1) {
      await page.mouse.move(area.x + area.width * .8, area.y + area.height * .5);
      await page.mouse.down();
      await page.mouse.move(area.x + area.width * .15, area.y + area.height * .5, { steps: 8 });
      await page.mouse.up();
      await page.waitForTimeout(180);
    }
    const chip = map.locator("[data-edge-chip]");
    await expect(chip).toHaveCount(1);
    await expect(chip).toContainText("1 · 2 · 3");
    for (const number of [1, 2, 3]) {
      await expect(pin(page, `${number}.`)).toHaveCount(1);
      await expect(pin(page, `${number}.`)).toHaveAttribute("aria-hidden", "true");
      await expect(pin(page, `${number}.`).locator("[data-pin-body]")).toBeHidden();
    }
    // OSM은 마커 본체 3개 + 아래 연결선 3개가 각각 기존 DOM에 남아 있다.
    await expect(map.locator('.leaflet-marker-icon[data-edge-hidden="true"]')).toHaveCount(6);
    await expect(map.locator("[data-pin-body][data-visibility-identity]")).toHaveCount(3);
    expect(await map.locator(".trip-route-line").count()).toBe(linesBefore);
    await map.screenshot({ path: test.info().outputPath(`distance-chip-${width}.png`) });
    // 칩의 기존 선택 동작은 유지된다. 묶음의 첫 장소로 이동하면 그 마커가 복구된다.
    await chip.click();
    await expect(pin(page, "1.")).toHaveAttribute("aria-pressed", "true");
    await expect(pin(page, "1.").locator("[data-pin-body]")).toBeVisible();
    await expect(pin(page, "1.")).toHaveAttribute("data-edge-hidden", "false");
    await expect(map.locator("[data-pin-body][data-visibility-identity]")).toHaveCount(3);
    await map.hover({ position: { x: area.width * .5, y: area.height * .5 } });
    await map.getByRole("button", { name: "모든 일정 보기", exact: true }).click({ force: true });
    await expect(map.locator("[data-edge-chip]")).toHaveCount(0);
    for (const number of [1, 2, 3]) await expect(pin(page, `${number}.`).locator("[data-pin-body]")).toBeVisible();
    await expect(map.locator('.leaflet-marker-icon[data-edge-hidden="true"]')).toHaveCount(0);
    await map.screenshot({ path: test.info().outputPath(`restored-markers-${width}.png`) });
  });
}
