import { expect, test } from "@playwright/test";

/** The plan-check preview runs on example data — a live build must not serve it to customers. */
test("live 빌드에서는 계획 확인 미리보기 주소가 열리지 않는다(404)", async ({ page }) => {
  const response = await page.goto("/preview/plan-check");
  expect(response?.status()).toBe(404);
  await expect(page.getByText("미리보기 · 예시 데이터 · 서버 미연결")).toHaveCount(0);
});
