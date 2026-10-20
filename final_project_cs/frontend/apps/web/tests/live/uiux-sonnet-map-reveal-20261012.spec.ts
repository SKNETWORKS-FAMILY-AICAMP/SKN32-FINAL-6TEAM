import { expect, test } from "@playwright/test";
import { checkPlan, mockServer, noHorizontalScroll, start } from "./helpers";
import { patchIntake, type Json } from "./plan-check-kit";
import { useMapTiles } from "./capture-map-tiles";

test.use({ video: "on" });

// 양쪽 방향과 같은 방향 모두 실제 SSE·최종 조회를 바꿔 카메라 이동까지 검사합니다.
const scenes = [{ name: "서쪽 두 일정", locations: {
  "0-0": { latitude: 37.5796, longitude: 126.9770 },
  "0-1": { latitude: 37.5798, longitude: 126.9773 },
  "0-2": { latitude: 37.5700, longitude: 127.0400 },
}, expectedSides: ["left", "left"] }, { name: "서쪽 1번·동쪽 2번", locations: {
  "0-0": { latitude: 37.5700, longitude: 126.9770 },
  "0-1": { latitude: 37.5700, longitude: 127.0800 },
  "0-2": { latitude: 37.5700, longitude: 127.0400 },
}, expectedSides: ["left", "right"] }];
const submittedPlan = "10/1 09:00 경복궁 관람";
for (const scene of scenes) {
const locations: Record<string, { latitude: number; longitude: number }> = scene.locations;
function spread(view: Json) {
  if (view.sources) expect(view.sources[0]?.lines[0]?.text, "제출 원문과 조회 원문이 같아야 순차 표시를 검사할 수 있어요").toBe(submittedPlan);
  for (const item of view.review?.items ?? []) {
    if (item.place && locations[item.id]) Object.assign(item.place, locations[item.id]);
  }
}

for (const width of [375, 1280]) {
  test(`세 번째 일정 공개 중 ${scene.name}은 실제 방향의 거리 스택으로 남는다 ${width}px`, async ({ page, request }) => {
    test.setTimeout(60000);
    await page.setViewportSize({ width, height: 812 });
    await page.emulateMedia({ reducedMotion: "no-preference" });
    const api = mockServer(request);
    await api.reset();
    // `[2026-10-20 C안]` 확인이 필요한 일정이 있으면 첫 검사가 그 카드에서 멈춰 묻는다 — 재생 · 지도를 보는 이 시험은 고칠 것이 없는 판(`calm`)으로 끝까지 본다.
    await api.scenario({ questions: "none", readingPolls: 999, board: "calm", review: "on" });
    const tilesReady = await useMapTiles(page);
    await start(page);
    await patchIntake(page, spread);
    let release!: () => void;
    const ready = new Promise<void>(resolve => { release = resolve; });
    await page.route("**/v1/web/trip-intakes/*/events", async route => {
      const response = await route.fetch();
      await ready;
      const body = (await response.text()).replace(/^data: (.+)$/gm, (_, raw) => {
        const packet = JSON.parse(raw);
        if (packet.place && locations[packet.id]) Object.assign(packet.place, locations[packet.id]);
        if (packet.state) spread(packet.state);
        return `data: ${JSON.stringify(packet)}`;
      });
      await route.fulfill({ response, body });
    });
    await page.goto("/trips/new");
    // mock 서버의 sources.lines 원문과 일치해야 원문 교체용 즉시 갱신 경로로 빠지지 않습니다.
    // rich 장면은 이 원문에도 실제 SSE로 세 일정을 반환합니다.
    await page.getByLabel("나의 여행 계획").fill(submittedPlan);
    await expect(page.getByLabel("나의 여행 계획")).toHaveValue(submittedPlan);
    await checkPlan(page);
    await expect(page.getByRole("heading", { name: "계획을 확인하고 있어요", exact: true })).toBeVisible();
    await api.scenario({ readingPolls: 0 });
    release();

    const map = page.getByRole("region", { name: "여행 지도", exact: true });
    const marker = (label: string) => map.locator(`.leaflet-marker-icon[title^="${label}."]`);
    await expect(marker("1")).toBeVisible({ timeout: 30000 });
    await marker("1").evaluate(node => { node.dataset.continuityProof = "first"; });
    await page.evaluate(expectedSides => {
      const log = { frames: 0, thirdFrames: 0, separatePreviousFrames: 0, completeThirdFrame: null as null | { chips: string[][]; centerDelta: [number, number]; previousHidden: boolean[]; previousRetained: boolean[] }, failureCount: 0, failures: [] as string[], stop: false };
      Object.assign(window, { __sonnetRevealLog: log });
      const seen = new Set<string>();
      const fail = (message: string) => { log.failureCount += 1; if (log.failures.length < 30) log.failures.push(message); };
      const sample = () => {
        if (log.stop) return;
        const map = document.querySelector('[aria-label="여행 지도"]');
        if (map && document.querySelector('[data-stage="checking"]')) {
          log.frames += 1;
          const area = map.getBoundingClientRect();
          const chipNodes = [...map.querySelectorAll<HTMLElement>('[data-edge-chip]')];
          const chips = chipNodes.map(chip => (chip.getAttribute("aria-label") ?? "").split("번 일정")[0].split(" · "));
          const pin = (label: string) => map.querySelector<HTMLElement>(`.leaflet-marker-icon[title^="${label}."]`);
          for (const label of ["1", "2"]) {
            const node = pin(label);
            if (node) seen.add(label);
            if (!seen.has(label)) continue;
            const inChip = chips.some(ids => ids.includes(label));
            if (!node) { if (!inChip) fail(`${label}: no marker or edge button`); continue; }
            const box = node.getBoundingClientRect();
            const x = box.x + box.width / 2 - area.x, y = box.y + box.height / 2 - area.y;
            const inside = x > 20 && x < area.width - 20 && y > 20 && y < area.height - 20;
            const outside = x < -20 || x > area.width + 20 || y < -20 || y > area.height + 20;
            if (node.dataset.edgeHidden === "true" && !inChip) fail(`${label}: hidden without an edge button`);
            if (outside && !inChip) fail(`${label}: outside without an edge button`);
            if (inside && node.dataset.edgeHidden === "true") fail(`${label}: inside marker hidden`);
          }
          if (pin("3")) {
            log.thirdFrames += 1;
            if (expectedSides[0] !== expectedSides[1] && chips.some(ids => ids.includes("1") && ids.includes("2"))) fail("opposite directions merged while revealing 3");
            if (chips.some(ids => ids.includes("3") && ids.length > 1)) fail("current 3 merged with a previous stop");
            if (chips.some(ids => ids.includes("1")) && chips.some(ids => ids.includes("2"))) log.separatePreviousFrames += 1;
            const third = pin("3")!;
            const box = third.getBoundingClientRect();
            const centerDelta: [number, number] = [Math.abs(box.x + box.width / 2 - area.x - area.width / 2), Math.abs(box.y + box.height / 2 - area.y - area.height / 2)];
            const previousHidden = ["1", "2"].map(label => pin(label)?.dataset.edgeHidden === "true");
            const previousRetained = ["1", "2"].map((label, at) => pin(label)?.dataset.continuityProof === (at === 0 ? "first" : "second"));
            const separate = ["1", "2"].every(label => {
              const matches = chipNodes.filter((_, at) => chips[at].includes(label));
              const chip = matches[0], style = chip && getComputedStyle(chip), bounds = chip?.getBoundingClientRect();
              return matches.length === 1 && style?.display !== "none" && style?.visibility !== "hidden" && !!bounds && bounds.width > 0 && bounds.height > 0;
            });
            const sides = ["1", "2"].map(label => chipNodes.find((_, at) => chips[at].includes(label))?.dataset.side);
            // 이동 완료, 두 이전 번호의 실제 방향, 현재 마커의 중심을 같은 공개 프레임에서 확인합니다.
            if (!map.hasAttribute("data-moving") && separate && previousHidden.every(Boolean) && previousRetained.every(Boolean)
              && third.dataset.edgeHidden !== "true" && centerDelta.every(delta => delta < 3)) {
              if (expectedSides[0] === expectedSides[1] && !chips.some(ids => ids.includes("1") && ids.includes("2"))) fail("same direction not stacked");
              if (sides.some((side, at) => side !== expectedSides[at])) fail(`wrong geographic side: ${JSON.stringify(sides)}`);
              log.completeThirdFrame = { chips, centerDelta, previousHidden, previousRetained };
            }
          }
        }
        requestAnimationFrame(sample);
      };
      requestAnimationFrame(sample);
    }, scene.expectedSides);
    try {
      await expect(marker("2")).toBeVisible();
      await marker("2").evaluate(node => { node.dataset.continuityProof = "second"; });
      await expect(marker("3")).toBeVisible();
      await page.waitForFunction(() => (window as unknown as { __sonnetRevealLog: { completeThirdFrame: unknown } }).__sonnetRevealLog.completeThirdFrame !== null, undefined, { timeout: 15000 });
      await expect(marker("1")).toHaveAttribute("data-continuity-proof", "first");
      await expect(marker("2")).toHaveAttribute("data-continuity-proof", "second");
      await tilesReady();
      // 투명한 SDK 마커 박스뿐 아니라 실제 번호 본체도 중앙에서 밀려나지 않아야 합니다.
      await expect(marker("3").locator("[data-push]")).toHaveAttribute("data-push", "0");
      const bodyDelta = await marker("3").locator("[data-pin-body]").evaluate(node => {
        const map = node.closest('[aria-label="여행 지도"]')!.getBoundingClientRect(), body = node.getBoundingClientRect();
        return [Math.abs(body.x + body.width / 2 - map.x - map.width / 2), Math.abs(body.y + body.height / 2 - map.y - map.height / 2)];
      });
      expect(bodyDelta.every(delta => delta < 23), JSON.stringify(bodyDelta)).toBe(true);
      await test.info().attach("current-pin-body-center", { body: JSON.stringify({ bodyDelta, expectedSides: scene.expectedSides }), contentType: "application/json" });
      await noHorizontalScroll(page);
      await page.screenshot({ path: test.info().outputPath(`after-third-frame-observed-${width}.png`) });
      await expect(page.locator('[data-stage="done"]')).toBeVisible();
      await expect(map).not.toHaveAttribute("data-moving");
      for (const label of ["1", "2", "3"]) await expect(marker(label)).toBeVisible();
      await expect(map.locator("[data-edge-chip]")).toHaveCount(0);
      const log = await page.evaluate(() => (window as unknown as { __sonnetRevealLog: { frames: number; thirdFrames: number; separatePreviousFrames: number; completeThirdFrame: unknown; failureCount: number; failures: string[] } }).__sonnetRevealLog);
      expect(log.frames).toBeGreaterThan(0);
      expect(log.thirdFrames).toBeGreaterThan(0);
      expect(log.separatePreviousFrames).toBeGreaterThan(0);
      expect(log.completeThirdFrame).not.toBeNull();
      expect(log.failureCount, JSON.stringify(log.failures)).toBe(0);
      await noHorizontalScroll(page);
    } finally {
      const log = await page.evaluate(() => {
        const log = (window as unknown as { __sonnetRevealLog: { stop: boolean } }).__sonnetRevealLog;
        log.stop = true;
        return log;
      });
      await test.info().attach("previous-two-reveal-frame-evidence", { body: JSON.stringify(log), contentType: "application/json" });
    }
  });
}
}
