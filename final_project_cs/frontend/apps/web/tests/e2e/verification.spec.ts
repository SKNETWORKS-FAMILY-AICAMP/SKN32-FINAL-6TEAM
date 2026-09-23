import { expect, test, type Page } from "@playwright/test";

async function loadSamplePlan(page: Page) {
  await page.goto("/");
  await page.getByRole("link", { name: "+ 첫 여행 등록하기" }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await page.getByRole("button", { name: "예시 계획 불러오기" }).click();
  const source = await page.locator("#plan-source").inputValue();
  expect(source).toContain("1일차 · 2026-09-15");
  expect(source).toContain("2일차 · 2026-09-16");
  return source;
}

async function submitPlan(page: Page) {
  await page.getByRole("button", { name: "검증 하기 →" }).click();
  await expect(page).toHaveURL(/\/trips\/[^/]+\/verification$/);
}

async function openCompletedResults(page: Page) {
  await expect(page.getByRole("progressbar", { name: "전체 검증 진행률" })).toHaveAttribute("aria-valuenow", "100");
  // Completion waits for the user's action; it must not redirect by itself.
  await expect(page).toHaveURL(/\/verification$/);
  await page.getByRole("link", { name: "결과 확인" }).click();
  await expect(page).toHaveURL(/\/results$/);
}

test("예시 계획을 새로고침 후에도 검증하고 여러 결과를 확인한 뒤 여행 홈을 연다", async ({ page }) => {
  await loadSamplePlan(page);
  await submitPlan(page);
  const progress = page.getByRole("progressbar", { name: "전체 검증 진행률" });
  await expect(progress).toBeVisible();
  await expect(page.getByRole("button", { name: "결과 확인" })).toBeDisabled();
  const initialProgress = Number(await progress.getAttribute("aria-valuenow"));
  expect(initialProgress).toBeLessThan(100);
  const verificationUrl = page.url();

  await page.reload();
  await expect(page).toHaveURL(verificationUrl);
  await expect(progress).toBeVisible();
  await expect.poll(async () => Number(await progress.getAttribute("aria-valuenow"))).toBeGreaterThan(initialProgress);
  await openCompletedResults(page);

  await expect(page.getByText("전체 검증 완료 · 결과 14건", { exact: true })).toBeVisible();
  await expect(page.locator("details")).toHaveCount(14);
  await expect(page.getByRole("heading", { name: "1일차", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "2일차", exact: true })).toBeVisible();
  const shopping = page.locator("details").filter({ has: page.getByText("성수동 쇼핑", { exact: true }) });
  await shopping.locator("summary").click();
  await expect(shopping.getByText("11:00", { exact: true })).toBeVisible();
  await expect(shopping.getByText("11:15", { exact: true })).toBeVisible();
  await expect(shopping.getByText("다른 일정에 미치는 영향", { exact: true })).toBeVisible();

  const start = page.getByRole("button", { name: "여행 관리 시작", exact: true });
  await expect(start).toBeDisabled();
  await page.getByRole("checkbox").check();
  await expect(start).toBeEnabled();
  await start.click();
  await expect(page).toHaveURL(/\/trips\/[0-9a-f-]+$/);
  await expect(page.getByRole("heading", { name: "서울, 취향을 따라 걷는 이틀", exact: true })).toBeVisible();
  await expect(page.getByText("여행을 등록했어요 · 시작 대기", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "1일차 일정", exact: true })).toBeVisible();

  await page.getByRole("link", { name: "검증 결과 다시 보기" }).click();
  await expect(page.getByRole("button", { name: "여행 관리 시작", exact: true })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "여행 홈으로" })).toBeVisible();
});

test("검증이 100%여도 미확인 항목이 있으면 동의 후에도 여행 관리를 시작할 수 없다", async ({ page }) => {
  await loadSamplePlan(page);
  await page.getByText("데모 검증 응답 설정", { exact: true }).click();
  await page.locator("#demo-scenario").selectOption("needs-review");
  await submitPlan(page);
  await expect(page.getByRole("heading", { name: "확인이 필요한 항목이 있어요", exact: true })).toBeVisible();
  await openCompletedResults(page);

  await expect(page.getByText("전체 검증 미완료 · 결과 14건", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "먼저 확인해 주세요", exact: true })).toBeVisible();
  const firstResult = page.locator("details").first();
  await expect(firstResult.locator("summary")).toContainText("확인 필요");
  await expect(firstResult.locator("summary")).toContainText("호텔 복귀");
  await expect(firstResult.getByText("미확인 이유", { exact: true })).toBeVisible();
  await page.getByRole("checkbox").check();
  await expect(page.getByText("미확인 항목 1건이 남아 있어요.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "여행 관리 시작", exact: true })).toBeDisabled();
  await expect(page.locator("details")).toHaveCount(14);
});

test("55% 검증 실패를 다시 시도하면 같은 여행의 전체 결과와 입력 원본이 보존된다", async ({ page }) => {
  const source = await loadSamplePlan(page);
  await page.getByText("데모 검증 응답 설정", { exact: true }).click();
  await page.locator("#demo-scenario").selectOption("failed");
  await submitPlan(page);
  const verificationUrl = page.url();

  await expect(page.getByRole("heading", { name: "검증이 잠시 중단되었어요", exact: true })).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "전체 검증 진행률" })).toHaveAttribute("aria-valuenow", "55");
  await expect(page.locator("#main-content").getByRole("alert")).toContainText("입력한 계획은 보존");
  await page.getByRole("button", { name: "검증 다시 시도", exact: true }).click();
  await expect(page).toHaveURL(verificationUrl);
  await expect(page.getByRole("heading", { name: "여행 계획을 확인하고 있어요", exact: true })).toBeVisible();
  await openCompletedResults(page);
  await expect(page).toHaveURL(verificationUrl.replace(/verification$/, "results"));
  await expect(page.getByText("전체 검증 완료 · 결과 14건", { exact: true })).toBeVisible();
  await expect(page.locator("details")).toHaveCount(14);
  await expect(page.getByRole("heading", { name: "먼저 확인해 주세요", exact: true })).toHaveCount(0);

  await page.getByRole("link", { name: "조건 수정 후 다시 검증", exact: true }).click();
  await expect(page).toHaveURL(/\/trips\/new\?from=/);
  await expect(page.locator("#plan-source")).toHaveValue(source);
});
