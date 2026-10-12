import { expect, test } from "@playwright/test";
import { edgeChips } from "../../src/features/map/map-geometry";
import { mockServer } from "./helpers";
import { openFinished } from "./plan-check-kit";

// 실제 화면이 만든 거리 단추의 DOM·제품 CSS를 재사용하는 배치 진단입니다.
// SSE/React 상태 전이는 별도 map-reveal 시험이 담당하며 여기서는 번호가 실제로 눌리는지 봅니다.
for (const count of [4, 5]) {
  test(`180px 지도에서 이전 ${count}개 거리 단추의 번호 중심을 누를 수 있다`, async ({ page, request }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await mockServer(request).reset();
    await openFinished(page, request);
    const map = page.getByRole("region", { name: "여행 지도", exact: true });
    await map.getByRole("button", { name: "지도 단추 펼치기", exact: true }).click();
    for (let i = 0; i < 8 && !(await map.locator("[data-edge-chip]").count()); i += 1) {
      await map.getByRole("button", { name: "확대", exact: true }).click();
      await expect(map).not.toHaveAttribute("data-moving");
    }
    await expect(map.locator("[data-edge-chip]").first()).toBeVisible();
    const view = { south: 37.5435, west: 126.9575, north: 37.5895, east: 126.9985, width: 360, height: 180, zoom: 13 };
    const points = Array.from({ length: count + 1 }, (_, index) => ({ id: String(index + 1), title: "일정", date: "", time: "", order: index + 1,
      coordinates: { lat: index === count ? 37.5665 : 37.61, lng: 126.978 }, revealFocus: index === count }));
    const chips = edgeChips(view, points, { top: 64, bottom: 76 });
    const evidence = await map.locator("[data-edge-chip]").first().evaluate((template, chips) => {
      const harness = document.createElement("div");
      Object.assign(harness.style, { position: "fixed", left: "0", top: "200px", width: "360px", height: "180px", zIndex: "100000", background: "white" });
      harness.dataset.crowdedProbe = "true";
      document.body.append(harness);
      const buttons = chips.map(chip => {
        const button = template.cloneNode(true) as HTMLElement;
        button.dataset.side = chip.x < 180 ? "left" : "right";
        if (chip.crowded) button.dataset.crowded = "true"; else delete button.dataset.crowded;
        button.querySelector('[class*="edgeNumbers"]')!.textContent = chip.labels[0];
        button.querySelector("small")!.textContent = "4.8km";
        button.style.left = `${chip.x}px`;
        button.style.top = `${chip.y}px`;
        harness.append(button);
        // 실제 컴포넌트와 같이 측정한 절반 폭으로 물리적 지도 밖만 보정합니다.
        const half = button.getBoundingClientRect().width / 2;
        const edge = chip.x >= 313 ? 360 - half : chip.x <= 47 ? half : chip.x;
        button.style.left = `${Math.min(360 - half, Math.max(half, edge))}px`;
        return button;
      });
      return buttons.map((button, index) => {
        const number = button.querySelector('[class*="edgeNumbers"]')!;
        const box = number.getBoundingClientRect();
        const x = box.x + box.width / 2, y = box.y + box.height / 2;
        return { id: chips[index].ids[0], button: button.getBoundingClientRect().toJSON(), number: box.toJSON(),
          numberCentreHitsOwnButton: document.elementFromPoint(x, y)?.closest("[data-edge-chip]") === button };
      });
    }, chips);
    await test.info().attach("crowded-number-hit-evidence", { body: JSON.stringify(evidence), contentType: "application/json" });
    await page.screenshot({ path: test.info().outputPath(`crowded-number-${count}.png`) });
    expect(evidence.every(entry => entry.numberCentreHitsOwnButton), JSON.stringify(evidence)).toBe(true);
    evidence.slice(1).forEach((entry, index) => expect(entry.button.left - evidence[index].button.right).toBeGreaterThanOrEqual(6));
  });
}
