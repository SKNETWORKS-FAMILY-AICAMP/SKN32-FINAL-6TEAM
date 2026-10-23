import { expect, test } from "@playwright/test";
import { mockServer } from "./helpers";
import { openFinished, timeBox, typeTimes } from "./plan-check-kit";

/**
 * `[2026-10-14 x600 실서버 확인]` 시간 고치기 창의 모양 두 가지.
 * ① 창을 열어도 그날 다른 카드가 창 높이만큼 빈 채로 늘어나지 않는다(「접힌 카드는 그날 가장 긴 카드 높이로」가 열린 창까지 세던 것).
 * ② 휴대폰 폭(375px)에서 시작 · 끝 칸의 시각이 잘리지 않는다(19px 글자로는 「오후 12:3」까지만 보였다).
 * mock 서버 시험이다 — 화면 반응을 본다.
 */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

test("시간 고치기 창을 열어도 다른 카드의 높이는 그대로다", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await openFinished(page, request);
  const other = page.locator("li[data-rail='stay'] > article").nth(1);
  await expect(other).toBeVisible();
  const before = (await other.boundingBox())!.height;
  await page.getByRole("button", { name: /^경복궁 관람 시간 고치기/ }).click();
  const form = page.getByRole("form", { name: "경복궁 관람 시간 고치기" });
  await expect(form).toBeVisible();
  await page.waitForTimeout(400);                                                                   // 줄 높이 맞춤이 한 번 돈 뒤
  const after = (await other.boundingBox())!.height;
  expect(after).toBeLessThanOrEqual(before + 2);                                                     // ★창 높이만큼 늘지 않는다
});

test.describe("휴대폰 폭 · 한국어", () => {
  test.use({ locale: "ko-KR" });                                                                   // 시험 브라우저 기본은 en-US 라 「09:00 AM」으로 보여 잘림이 안 드러난다

  test("시작 · 끝 칸의 안쪽 폭이 「오후 12:30」이 들어갈 만큼 넓다", async ({ page, request }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await openFinished(page, request);
    await page.getByRole("button", { name: /^경복궁 관람 시간 고치기/ }).click();
    const form = page.getByRole("form", { name: "경복궁 관람 시간 고치기" });
    // `[2026-10-21 ST4F-702]` 창은 휠로 열린다 — 머리의 시작 · 끝 칸 글자(「오전 9:00」 꼴)가 잘리지 않고, ⌨ 를 누르면 나오는 입력칸도 넓다
    for (const word of ["시작", "끝"] as const) {
      const fits = await timeBox(form, word).evaluate((element) => [...element.children].every((child) => child.scrollWidth <= (element as HTMLElement).clientWidth));
      expect(fits).toBe(true);
    }
    await typeTimes(form);
    for (const name of ["시작", "끝"]) {
      const input = form.getByLabel(name, { exact: true });
      await expect(input).toBeVisible();
      const box = await input.evaluate((element) => {
        const style = getComputedStyle(element);
        return { inner: element.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight), font: parseFloat(style.fontSize) };
      });
      // 시간 입력의 글자 폭은 밖에서 잴 수 없다(scrollWidth 가 따라가지 않는다). x600 실서버 캡처(19px 굵은 글자 · 안쪽 약 87px 에 「오후 12:3」까지)로
      // 「오후 12:30」이 글자 크기의 약 5.2배임을 재었다 — 5.3배를 넘으면 들어간다
      expect(box.inner).toBeGreaterThanOrEqual(box.font * 5.3);
    }
  });
});
