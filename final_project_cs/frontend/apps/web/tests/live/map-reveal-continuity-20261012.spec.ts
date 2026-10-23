import { expect, test } from "@playwright/test";
import { checkPlan, mockServer, noHorizontalScroll, start } from "./helpers";
import { patchIntake, type Json } from "./plan-check-kit";
import { useMapTiles } from "./capture-map-tiles";

test.use({ video: "on" });

function spread(view: Json) {
  if (!view.review) return;
  view.review.items[1].place.longitude = 127.02;
}

for (const width of [375, 1280]) {
 for (const reduced of [false, true]) {
  test.describe(`${width}px 순서대로 지도 표시 · 동작 줄이기 ${reduced}`, () => {
    test.use({ viewport: { width, height: 812 } });
    test("먼 이전 마커는 거리 표시로 남고 새 마커와 합쳐지지 않는다", async ({ page, request }) => {
      test.setTimeout(60000);
      const api = mockServer(request);
      await api.reset();
      // `[2026-10-20 C안]` 확인이 필요한 일정이 있으면 첫 검사가 그 카드에서 멈춰 묻는다 — 재생 · 지도를 보는 이 시험은 고칠 것이 없는 판(`calm`)으로 끝까지 본다.
      await api.scenario({ questions: "none", readingPolls: 999, board: "calm", review: "on" });
      await page.emulateMedia({ reducedMotion: reduced ? "reduce" : "no-preference" });
      await start(page);
      await patchIntake(page, spread);
      const tilesReady = process.env.REVEAL_CAPTURE === "1" ? await useMapTiles(page) : null;
      let release!: () => void;
      const ready = new Promise<void>(resolve => { release = resolve; });
      await page.route("**/v1/web/trip-intakes/*/events", async route => {
        const response = await route.fetch();
        await ready;
        const body = (await response.text()).replace(/^data: (.+)$/gm, (_, raw) => {
          const packet = JSON.parse(raw);
          if (packet.id === "0-1" && packet.place) packet.place.longitude = 127.02;
          if (packet.state) spread(packet.state);
          return `data: ${JSON.stringify(packet)}`;
        });
        await route.fulfill({ response, body });
      });
      await page.goto("/trips/new");
      await page.getByLabel("나의 여행 계획").fill("10/1 09:00 경복궁 관람");
      await checkPlan(page);
      await expect(page.getByRole("heading", { name: "계획을 확인하고 있어요", exact: true })).toBeVisible();
      await api.scenario({ readingPolls: 0 });
      release();
      const map = page.getByRole("region", { name: "여행 지도", exact: true });
      const marker = (label: string) => map.locator(`.leaflet-marker-icon[title^="${label}."]`);
      await expect(marker("1")).toBeVisible({ timeout: 30000 });
      await marker("1").evaluate(node => { node.dataset.continuityProof = "kept"; });
      await page.evaluate(() => {
        const log = { failures: [] as string[], positions: [] as string[], animations: [] as number[], stop: false };
        Object.assign(window, { __revealLog: log });
        const sample = () => {
          const map = document.querySelector('[aria-label="여행 지도"]');
          if (!map || log.stop) return;
          const area = map.getBoundingClientRect();
          if (document.querySelector('[data-stage="checking"]')) {
            const labels = [...map.querySelectorAll<HTMLElement>('[data-pin-label]')].map(body => Number(body.dataset.pinLabel));
            const newest = String(Math.max(...labels));
            for (const chip of map.querySelectorAll('[data-edge-chip]')) {
              const ids = (chip.getAttribute('aria-label') ?? '').split('번 일정')[0].split(' · ');
              if (ids.length > 1 && ids.includes(newest)) log.failures.push(`newest merged: ${ids.join(',')}`);
            }
          }
          for (const pin of map.querySelectorAll<HTMLElement>('.leaflet-marker-icon[title]')) {
            const box = pin.getBoundingClientRect(), x = box.x + box.width / 2 - area.x, y = box.y + box.height / 2 - area.y;
            const label = pin.querySelector<HTMLElement>('[data-pin-label]')?.dataset.pinLabel;
            if (label === "2") log.positions.push(`${Math.round(x)},${Math.round(y)}`);
            if (x > 20 && x < area.width - 20 && y > 20 && y < area.height - 20 && pin.dataset.edgeHidden === "true") log.failures.push(JSON.stringify({ label, x, y, at: performance.now(), transform: pin.style.transform, chips: [...map.querySelectorAll('[data-edge-chip]')].map(chip => chip.getAttribute('aria-label')) }));
            for (const animation of pin.getAnimations({ subtree: true })) log.animations.push(Number(animation.effect?.getTiming().duration));
          }
          requestAnimationFrame(sample);
        };
        requestAnimationFrame(sample);
      });
      await page.screenshot({ path: test.info().outputPath(`step-1-${width}.png`) });
      await expect(marker("2")).toBeVisible();
      await expect(map).not.toHaveAttribute("data-moving");
      const old = map.locator('[data-edge-chip]').filter({ hasText: "1" });
      await expect(old).toHaveAttribute("aria-label", /^1번 일정이 화면 밖에 있어요 · [\d.]+[km]+/);
      await expect(old.locator("small")).toBeVisible();
      await expect(marker("2")).not.toHaveAttribute("data-edge-hidden", "true");
      await expect(marker("1")).toHaveAttribute("data-continuity-proof", "kept");
      const area = (await map.boundingBox())!, pin = (await marker("2").boundingBox())!;
      expect(Math.abs(pin.x + pin.width / 2 - area.x - area.width / 2)).toBeLessThan(3);
      expect(Math.abs(pin.y + pin.height / 2 - area.y - area.height / 2)).toBeLessThan(3);
      await page.screenshot({ path: test.info().outputPath(`step-2-${width}.png`) });
      await expect(marker("3")).toBeVisible();
      await expect(map).not.toHaveAttribute("data-moving");
      await page.screenshot({ path: test.info().outputPath(`step-3-${width}.png`) });
      await expect(page.locator('[data-stage="done"]')).toBeVisible();
      await expect(map).not.toHaveAttribute("data-moving");
      await expect(marker("1")).toBeVisible();
      await expect(marker("2")).toBeVisible();
      await expect(marker("3")).toBeVisible();
      await expect(map.locator('[data-edge-chip]')).toHaveCount(0);
      const log = await page.evaluate(() => {
        const log = (window as unknown as { __revealLog: { failures: string[]; positions: string[]; animations: number[]; stop: boolean } }).__revealLog;
        log.stop = true; return log;
      });
      await test.info().attach("reveal-frame-evidence", { body: JSON.stringify(log), contentType: "application/json" });
      expect(log.failures).toEqual([]);
      if (reduced) expect(log.animations).toEqual([]);
      else { expect(new Set(log.positions).size).toBeGreaterThan(8); expect(log.animations).toContain(300); }
      if (tilesReady) await tilesReady();
      await page.screenshot({ path: test.info().outputPath(`step-done-${width}.png`) });
      await noHorizontalScroll(page);
    });
  });
 }
}
