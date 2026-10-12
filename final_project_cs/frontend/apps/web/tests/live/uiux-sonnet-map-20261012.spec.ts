import { expect, test } from "@playwright/test";
import { mockServer } from "./helpers";
import { mapSettled, openFinished } from "./plan-check-kit";

// mock 서버 시험: 좌표 선택 중 거리 버튼은 위치 지정으로 가로채지 않고 카메라를 이동합니다.
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });
for (const width of [375, 1280]) {
  test(`직접 위치 지정 중 먼 일정 버튼을 눌러도 새 좌표를 고르지 않는다 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await openFinished(page, request, undefined, { intakeEvents: "off" });
    const intro = page.getByRole("status").filter({ hasText: "계획 확인 화면이에요" });
    if (await intro.count()) await intro.getByRole("button", { name: "닫기", exact: true }).click();
    await page.locator("[data-insert-near] > button").click();
    await page.getByRole("button", { name: "지도에서 위치 지정", exact: true }).click();
    const picker = page.getByRole("region", { name: "지도에서 위치 지정", exact: true });
    await expect(picker).toBeVisible();
    await mapSettled(page);
    const unfold = page.getByRole("button", { name: "지도 단추 펼치기", exact: true });
    await unfold.click();
    const chip = page.locator("[data-edge-chip]").first();
    for (let at = 0; at < 6 && !(await chip.count()); at += 1) {
      await page.getByRole("button", { name: "확대", exact: true }).click();
      await expect(page.getByRole("region", { name: "여행 지도", exact: true })).not.toHaveAttribute("data-moving");
    }
    // 펼친 도구는 마커와 겹칠 수 있으므로 거리·접기 버튼만 남긴 다음 누릅니다.
    await page.getByRole("button", { name: "지도 단추 접기", exact: true }).click();
    await expect(chip).toBeVisible();
    await expect(page.locator("[data-coordinate-pin]")).toHaveCount(0);
    await chip.click();
    await expect(page.locator("[data-coordinate-pin]")).toHaveCount(0);
    await expect(picker.getByRole("button", { name: "이 위치 사용", exact: true })).toBeDisabled();
  });
}
