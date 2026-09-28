import { expect, test, type Page } from "@playwright/test";
import { openCompletedResults, startTrip, submitPlan, useKorean } from "./helpers/app";

test.beforeEach(async ({ page }) => { await useKorean(page); });

async function loadSamplePlan(page: Page, scenario?: "needs-review" | "failed") {
  await page.goto("/trips/new");
  await page.getByRole("button", { name: "예시 불러오기" }).click();
  const source = await page.locator("#plan-source").inputValue();
  expect(source).toContain("1일차 · 2026-09-15");
  expect(source).toContain("2일차 · 2026-09-16");
  if (scenario) {
    await page.getByText("데모 체험 옵션", { exact: true }).click();
    await page.locator("#demo-scenario").selectOption(scenario);
  }
  return source;
}

test("예시 계획을 새로고침 후에도 검증하고 일차별 결과를 확인한 뒤 여행 화면을 연다", async ({ page }) => {
  await loadSamplePlan(page);
  await submitPlan(page);
  const progress = page.getByRole("progressbar", { name: "계획 확인 진행률" });
  await expect(progress).toBeVisible();
  await expect(page.getByRole("button", { name: "결과 확인하기" })).toBeDisabled();
  const initialProgress = Number(await progress.getAttribute("aria-valuenow"));
  expect(initialProgress).toBeLessThan(100);
  const verificationUrl = page.url();

  await page.reload();
  await expect(page).toHaveURL(verificationUrl);
  await expect.poll(async () => Number(await progress.getAttribute("aria-valuenow"))).toBeGreaterThan(initialProgress);
  await expect(page.getByRole("heading", { name: "여행 계획을 살펴봤어요.", exact: true })).toBeVisible();
  await openCompletedResults(page);

  await expect(page.getByRole("heading", { name: "여행의 준비가 끝났어요.", exact: true })).toBeVisible();
  await expect(page.getByText("14개 일정", { exact: true })).toBeVisible();
  await expect(page.locator("details")).toHaveCount(7);
  const shopping = page.locator("details").filter({ has: page.getByText("성수동 쇼핑", { exact: true }) });
  await expect(shopping.locator("summary")).toContainText("11:00 → 11:15");
  await shopping.locator("summary").click();
  await expect(shopping.getByText("변경 전")).toBeVisible();
  await expect(shopping).toContainText("이동 여유 15분");
  await page.getByRole("button", { name: /2일차/ }).click();
  await expect(page.locator("details")).toHaveCount(7);
  await expect(page.locator("details").filter({ hasText: "이태원 소품숍" }).locator("summary")).toContainText("14:00 → 14:15");

  await startTrip(page);
  await expect(page.getByText("여행 관리 화면", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "1일차 일정", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "검증 결과 다시 보기" }).click();
  await expect(page.getByRole("button", { name: "여행 관리 시작" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "내 여행으로 돌아가기" })).toBeVisible();
});

test("검증이 100%여도 확인이 필요한 항목이 있으면 동의 후에도 여행 관리를 시작할 수 없다", async ({ page }) => {
  await loadSamplePlan(page, "needs-review");
  await submitPlan(page);
  await openCompletedResults(page);
  await expect(page.getByRole("heading", { name: "한 번 더 확인해 주세요.", exact: true })).toBeVisible();
  await expect(page.getByText("여행 관리를 시작하기 전에", { exact: true })).toBeVisible();
  const first = page.locator("details").first();
  await expect(first).toHaveAttribute("open", "");
  await expect(first.locator("summary")).toContainText("확인 필요");
  await expect(first.locator("summary")).toContainText("호텔 복귀");
  await page.getByRole("checkbox").check();
  await expect(page.getByText("미확인 항목을 해결해야 시작할 수 있어요.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "여행 관리 시작" })).toBeDisabled();
  await page.getByRole("button", { name: "검증 다시 시도" }).click();
  await expect(page).toHaveURL(/\/verification$/);
  await openCompletedResults(page);
  await expect(page.getByRole("heading", { name: "여행의 준비가 끝났어요.", exact: true })).toBeVisible();
});

test("55%에서 멈춘 검증을 다시 시도하면 같은 여행의 결과와 입력 원본이 보존된다", async ({ page }) => {
  const source = await loadSamplePlan(page, "failed");
  await submitPlan(page);
  const verificationUrl = page.url();
  await expect(page.getByRole("heading", { name: "잠시 쉬어가는 중이에요.", exact: true })).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "계획 확인 진행률" })).toHaveAttribute("aria-valuenow", "55");
  await expect(page.locator("#main-content").getByRole("alert")).toContainText("입력한 계획을 유지한 채");
  await page.goto(verificationUrl.replace(/verification$/, "results"));
  await expect(page.getByRole("heading", { name: "계획 확인이 아직 끝나지 않았어요" })).toBeVisible();
  await page.getByRole("link", { name: "확인 진행 보기" }).click();
  await page.getByRole("button", { name: "다시 시도하기", exact: true }).click();
  await expect(page).toHaveURL(verificationUrl);
  await expect(page.getByRole("heading", { name: "더 편한 여행을 준비해요.", exact: true })).toBeVisible();
  await openCompletedResults(page);
  await expect(page).toHaveURL(verificationUrl.replace(/verification$/, "results"));
  await expect(page.getByText("14개 일정", { exact: true })).toBeVisible();
  await expect(page.getByText("여행 관리를 시작하기 전에", { exact: true })).toHaveCount(0);

  await page.getByRole("link", { name: "계획 수정 후 다시 확인", exact: true }).click();
  await expect(page).toHaveURL(/\/trips\/new\?from=/);
  await expect(page.locator("#plan-source")).toHaveValue(source);
});

test("결과 화면에서 언어를 바꾸면 같은 결과가 영어로 다시 표시된다", async ({ page }) => {
  await loadSamplePlan(page);
  await submitPlan(page);
  await openCompletedResults(page);
  await page.getByRole("button", { name: "설정 메뉴" }).click();
  await page.getByRole("dialog", { name: "설정" }).getByText("English").click();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("heading", { name: "You’re ready for your journey.", exact: true })).toBeVisible();
  const shopping = page.locator("details").filter({ has: page.getByText("성수동 쇼핑", { exact: true }) });
  await shopping.locator("summary").click();
  await expect(shopping).toContainText("15-minute buffer");
  await expect(page).toHaveTitle("Your results · triPilot");
});
