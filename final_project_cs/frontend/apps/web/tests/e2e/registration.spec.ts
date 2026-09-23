import { expect, test } from "@playwright/test";

test("빈 입력과 잘못된 날짜를 안내하고 작성 중인 계획을 새로고침해도 보존한다", async ({ page }) => {
  await page.goto("/trips/new");
  await page.getByRole("button", { name: "검증 하기" }).click();
  await expect(page.locator("#main-content").getByRole("alert")).toHaveText("시간과 장소가 있는 여행 계획을 입력해 주세요.");
  const plan = page.getByLabel("여행 계획 필수");
  const invalid = "1일차 · 2026-02-30\n09:00 아침 식사";
  await plan.fill(invalid);
  await page.getByRole("button", { name: "검증 하기" }).click();
  await expect(page.locator("#main-content").getByRole("alert")).toContainText("올바른 날짜");
  await expect(page).toHaveURL(/\/trips\/new$/);
  const valid = "1일차 · 2026-10-03\n09:00 호텔 조식\n13:00 점심 식당 · 예약 있음";
  await plan.fill(valid);
  await page.getByRole("link", { name: "← 내 여행", exact: true }).click();
  await page.getByRole("link", { name: "+ 첫 여행 등록하기" }).click();
  await expect(plan).toHaveValue(valid);
  await page.reload();
  await expect(plan).toHaveValue(valid);
  await page.getByRole("button", { name: "검증 하기" }).click();
  await page.getByRole("link", { name: "결과 확인" }).click();
  await expect(page.getByText("전체 검증 완료 · 결과 2건", { exact: true })).toBeVisible();
  await expect(page.locator("details")).toHaveCount(2);
  await expect(page.locator("details").filter({ hasText: "점심 식당" })).toContainText("13:00 · 유지");
});

test("320px에서 등록과 결과를 읽을 수 있고 관리 시작 전 홈 접근은 안내한다", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 720 });
  await page.goto("/");
  await page.getByRole("link", { name: "+ 첫 여행 등록하기" }).click();
  await page.getByRole("button", { name: "예시 계획 불러오기" }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("button", { name: "검증 하기" }).click();
  await expect(page).toHaveURL(/\/trips\/[^/]+\/verification$/);
  const tripHome = page.url().replace(/\/verification$/, "");
  await page.goto(tripHome);
  await expect(page.getByRole("heading", { name: "여행 계획을 검증하고 있어요" })).toBeVisible();
  await page.getByRole("link", { name: "검증 진행 보기" }).click();
  await page.getByRole("link", { name: "결과 확인" }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.goto(tripHome);
  await expect(page.getByRole("heading", { name: "검증 결과를 먼저 확인해 주세요" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "여행 채팅" })).toHaveCount(0);
});
