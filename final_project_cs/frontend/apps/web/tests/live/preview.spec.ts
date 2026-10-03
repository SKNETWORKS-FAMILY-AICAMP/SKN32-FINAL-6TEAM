import { expect, test } from "@playwright/test";

/** ★`[2026-10-03]` The example-data screen (`/preview/plan-check`) was deleted from the app: no build serves it, so a customer can never reach one. */
test("예시 데이터로 도는 계획 확인 미리보기 주소는 이제 없다(404)", async ({ page }) => {
  const response = await page.goto("/preview/plan-check");
  expect(response?.status()).toBe(404);
  await expect(page.getByText("미리보기 · 예시 데이터 · 서버 미연결")).toHaveCount(0);
});
