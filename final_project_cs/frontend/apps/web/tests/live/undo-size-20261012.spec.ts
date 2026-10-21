import { expect, test, type Locator } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import { captureShots, mockServer, noHorizontalScroll } from "./helpers";
import { openFinished, typeTimes } from "./plan-check-kit";

async function metrics(control: Locator) {
  return control.evaluate(element => {
    const style = getComputedStyle(element);
    const box = element.getBoundingClientRect();
    return { width: box.width, height: box.height, fontSize: style.fontSize, padding: style.padding,
      hitHeight: getComputedStyle(element, "::after").height };
  });
}

for (const width of [375, 1280]) {
  test(`${width}px 장소·시간 되돌리기는 확인 필요 표시 크기이며 키보드 복원이 가능하다`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await mockServer(request).reset();
    await openFinished(page, request, undefined, { intakeEvents: "off" });
    const badge = page.locator('[data-card-footer-status] span').filter({ hasText: /^확인 필요$/ }).first();
    await expect(badge).toBeVisible();
    const reference = await metrics(badge);
    const first = page.locator("#plan-card-0-0");
    const title = first.getByRole("heading").getByRole("button");
    if (await title.getAttribute("aria-expanded") !== "true") await title.click();
    await page.locator("#plan-recommend-0-0").click();
    const undoPlace = first.getByRole("button", { name: /변경 되돌리기$/ });
    await expect(undoPlace).toBeVisible();
    const place = await metrics(undoPlace);
    expect(Math.abs(place.height - reference.height)).toBeLessThanOrEqual(1);
    expect(place.fontSize).toBe(reference.fontSize);
    expect(place.hitHeight).toBe("44px");
    await noHorizontalScroll(page);
    // `[2026-10-16 ⑤]` 갤러리 · 지표 파일은 UNDO_SIZE_SHOTS 나 CAPTURE_SHOTS=1 일 때만 남긴다
    const gallery = process.env.UNDO_SIZE_SHOTS ?? (captureShots ? "mockups/undo-size-20261012" : null);
    if (gallery) await mkdir(gallery, { recursive: true });
    if (gallery) await page.screenshot({ path: `${gallery}/place-${width}.png`, fullPage: true });
    await undoPlace.focus();
    await page.keyboard.press("Enter");
    await expect(first.getByRole("button", { name: /변경 되돌리기$/ })).toHaveCount(0);
    await page.getByRole("button", { name: /^경복궁 관람 시간 고치기/ }).click();
    const form = await typeTimes(page.getByRole("form", { name: "경복궁 관람 시간 고치기" }));
    await form.getByLabel("시작", { exact: true }).fill("09:10");
    await form.getByRole("button", { name: "적용", exact: true }).click();
    const undoTime = first.getByRole("button", { name: "경복궁 관람 시간 되돌리기" });
    await expect(undoTime).toBeVisible();
    const time = await metrics(undoTime);
    expect(Math.abs(time.height - reference.height)).toBeLessThanOrEqual(1);
    expect(time.fontSize).toBe(reference.fontSize);
    expect(time.hitHeight).toBe("44px");
    await noHorizontalScroll(page);
    if (gallery) await page.screenshot({ path: `${gallery}/time-${width}.png`, fullPage: true });
    if (gallery) await writeFile(`${gallery}/metrics-${width}.json`, JSON.stringify({ reference, place, time }, null, 2));
    await undoTime.focus();
    await page.keyboard.press("Enter");
    await expect(first.getByRole("button", { name: "경복궁 관람 시간 되돌리기" })).toHaveCount(0);
  });
}
