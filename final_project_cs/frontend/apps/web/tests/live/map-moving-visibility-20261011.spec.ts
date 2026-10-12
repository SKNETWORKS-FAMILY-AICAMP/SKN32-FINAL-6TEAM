import { expect, test, type Page } from "@playwright/test";
import { checkPlan, mockServer, noHorizontalScroll, start } from "./helpers";
import { openFinished } from "./plan-check-kit";
import { useMapTiles } from "./capture-map-tiles";

const map = (page: Page) => page.getByRole("region", { name: "여행 지도", exact: true });

async function observeFrames(page: Page) {
  await page.evaluate(() => {
    const log = { frames: 0, inside: 0, failures: [] as { label: string; hidden: boolean; chip: string; x: number; y: number }[], stop: false };
    Object.assign(window, { __movingPinLog: log });
    const sample = () => {
      if (log.stop) return;
      log.frames++;
      const element = document.querySelector('[role="region"][aria-label="여행 지도"]');
      if (!element) { requestAnimationFrame(sample); return; }
      const bounds = element.getBoundingClientRect();
      const chips = Array.from(element.querySelectorAll<HTMLElement>("[data-edge-chip]"));
      for (const pin of element.querySelectorAll<HTMLElement>(".leaflet-marker-icon")) {
        const body = pin.querySelector<HTMLElement>("[data-pin-label]");
        if (!body) continue;
        const box = pin.getBoundingClientRect(), x = box.x + box.width / 2 - bounds.x, y = box.y + box.height / 2 - bounds.y;
        // Stay clear of the geographic boundary to exclude projection/rounding noise.
        if (x < 20 || x > bounds.width - 20 || y < 20 || y > bounds.height - 20) continue;
        log.inside++;
        const label = body.dataset.pinLabel!;
        const chip = chips.find((node) => (node.getAttribute("aria-label") ?? "").split("번 일정")[0].split(" · ").includes(label));
        const hidden = pin.dataset.edgeHidden === "true";
        if ((chip || hidden) && log.failures.length < 20) log.failures.push({ label, hidden, chip: chip?.getAttribute("aria-label") ?? "", x, y });
      }
      requestAnimationFrame(sample);
    };
    requestAnimationFrame(sample);
  });
}

async function assertFrames(page: Page) {
  const log = await page.evaluate(() => {
    const log = (window as unknown as { __movingPinLog: { frames: number; inside: number; failures: unknown[]; stop: boolean } }).__movingPinLog;
    log.stop = true;
    return log;
  });
  expect(log.frames).toBeGreaterThan(5);
  expect(log.inside).toBeGreaterThan(0);
  expect(log.failures).toEqual([]);
  await test.info().attach("moving-pin-frames", { body: JSON.stringify(log), contentType: "application/json" });
  await noHorizontalScroll(page);
}

for (const width of [375, 1280]) {
  test(`${width}px 확대·축소하는 동안 보이는 마커를 숨기거나 거리 칩에 합치지 않는다`, async ({ page, request }) => {
    test.setTimeout(60000);
    await page.setViewportSize({ width, height: 1000 });
    await mockServer(request).reset();
    const tilesReady = await useMapTiles(page);
    await openFinished(page, request);
    const controls = map(page).getByRole("group", { name: "지도 단추", exact: true });
    await map(page).hover();
    await controls.getByRole("button", { name: "지도 단추 펼치기", exact: true }).click();
    await observeFrames(page);
    for (const name of ["확대", "확대", "축소"]) {
      await controls.getByRole("button", { name, exact: true }).click();
      await expect(map(page)).not.toHaveAttribute("data-moving", "true");
      await page.waitForTimeout(250);
    }
    await assertFrames(page);
    await tilesReady();
    await page.screenshot({ path: test.info().outputPath(`moving-map-${width}.png`) });
  });

  test(`${width}px 로딩 중 새 일정의 자동 지도 이동에서도 보이는 마커를 거리 칩에 합치지 않는다`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    const server = mockServer(request);
    await server.reset();
    await server.scenario({ questions: "none", readingPolls: 999, board: "rich", review: "on" });
    await start(page);
    let release!: () => void;
    const ready = new Promise<void>((resolve) => { release = resolve; });
    await page.route("**/v1/web/trip-intakes/*/events", async (route) => {
      const response = await route.fetch();
      await ready;
      await route.fulfill({ response });
    });
    await page.goto("/trips/new");
    await page.getByLabel("나의 여행 계획").fill("10/15 09:00 경복궁 관람");
    await checkPlan(page);
    await expect(page.getByRole("heading", { name: "계획을 확인하고 있어요", exact: true })).toBeVisible();
    await observeFrames(page);
    await server.scenario({ readingPolls: 0 });
    release();
    await expect(map(page).locator("[data-pin-body]")).toHaveCount(3, { timeout: 30000 });
    await expect(page.locator('[data-stage="done"]')).toBeVisible({ timeout: 30000 });
    await expect(map(page)).not.toHaveAttribute("data-moving");
    await page.waitForTimeout(250);
    await assertFrames(page);
  });

  test(`${width}px 지도 밖 묶음을 눌러 가운데로 들어오는 마커는 이동 중에도 거리 칩에서 빠진다`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 1000 });
    await mockServer(request).reset();
    await openFinished(page, request);
    const area = (await map(page).boundingBox())!;
    for (let step = 0; step < 5; step += 1) {
      await page.mouse.move(area.x + area.width * .8, area.y + area.height * .5);
      await page.mouse.down();
      await page.mouse.move(area.x + area.width * .15, area.y + area.height * .5, { steps: 8 });
      await page.mouse.up();
      await page.waitForTimeout(180);
    }
    const chip = map(page).locator("[data-edge-chip]");
    await expect(chip).toHaveCount(1);
    await expect(chip).toHaveAttribute("aria-label", /^1 · 2 · 3번 일정이 화면 밖에 있어요/);
    await observeFrames(page);
    await chip.click();
    await expect(map(page)).not.toHaveAttribute("data-moving");
    await page.waitForTimeout(250);
    await assertFrames(page);
  });
}
