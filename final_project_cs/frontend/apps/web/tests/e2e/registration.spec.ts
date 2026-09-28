import { expect, test } from "@playwright/test";
import { noHorizontalScroll, openCompletedResults, submitPlan, useKorean } from "./helpers/app";

test.beforeEach(async ({ page }) => { await useKorean(page); });

test("빈 입력과 잘못된 날짜를 안내하고 작성 중인 계획을 오가도·새로고침해도 보존한다", async ({ page }) => {
  await page.goto("/trips/new");
  const submit = page.getByRole("button", { name: "계획 확인하기" });
  await submit.click();
  await expect(page.locator("#main-content").getByRole("alert")).toHaveText("시간과 장소가 있는 여행 계획을 입력해 주세요.");
  const plan = page.getByLabel("나의 여행 계획");
  await plan.fill("1일차 · 2026-02-30\n09:00 아침 식사");
  await submit.click();
  await expect(page.locator("#main-content").getByRole("alert")).toContainText("올바른 날짜");
  await expect(page).toHaveURL(/\/trips\/new$/);
  const valid = "1일차 · 2026-10-03\n09:00 호텔 조식\n13:00 점심 식당 · 예약 있음";
  await plan.fill(valid);
  await page.locator("form").getByRole("link", { name: "홈으로" }).click();
  await expect(page).toHaveURL(/\/start$/);
  await page.goBack();
  await expect(plan).toHaveValue(valid);
  await page.reload();
  await expect(plan).toHaveValue(valid);
  await submitPlan(page);
  await openCompletedResults(page);
  await expect(page.getByRole("heading", { name: "여행의 준비가 끝났어요.", exact: true })).toBeVisible();
  await expect(page.locator("details")).toHaveCount(2);
  await expect(page.locator("details").filter({ hasText: "점심 식당" })).toContainText("13:00 · 입력한 시간");
});

test("320px에서 등록과 결과를 읽을 수 있고 관리 시작 전 여행 화면은 안내한다", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 720 });
  await page.goto("/");
  await noHorizontalScroll(page);
  await page.getByRole("button", { name: /소개 건너뛰기/ }).first().click();
  await page.getByRole("button", { name: "내 일정 시작하기" }).click();
  await expect(page).toHaveURL(/\/start$/);
  await noHorizontalScroll(page);
  await page.goto("/trips/new");
  await page.getByRole("button", { name: "예시 불러오기" }).click();
  await noHorizontalScroll(page);
  await submitPlan(page);
  const tripHome = page.url().replace(/\/verification$/, "");
  await page.goto(tripHome);
  await expect(page.getByRole("heading", { name: "여행 계획을 확인하고 있어요" })).toBeVisible();
  await page.getByRole("link", { name: "확인 진행 보기" }).click();
  await openCompletedResults(page);
  await noHorizontalScroll(page);
  await page.goto(tripHome);
  await expect(page.getByRole("heading", { name: "검증 결과를 먼저 확인해 주세요" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "여행 채팅" })).toHaveCount(0);
});
