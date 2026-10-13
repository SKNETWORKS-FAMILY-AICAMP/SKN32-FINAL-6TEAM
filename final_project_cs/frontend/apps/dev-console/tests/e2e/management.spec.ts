import { expect, test, type Page } from "@playwright/test";

const main = (page: Page) => page.locator("#main-content");
const selectedOccurrence = (page: Page) => main(page).getByRole("region", { name: "선택한 발생 상세" });

async function search(page: Page, query: string) {
  await main(page).getByLabel("오류 검색", { exact: true }).fill(query);
  await main(page).getByRole("button", { name: "검색", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`q=${encodeURIComponent(query)}`));
}

async function expectNoOverflow(page: Page) {
  const size = await page.evaluate(() => ({ viewport: window.innerWidth, content: document.documentElement.scrollWidth }));
  expect(size.content).toBeLessThanOrEqual(size.viewport);
}

test("관리 홈에서 오류를 검색하고 해당 발생 상세와 목록의 조건을 새로고침 후에도 유지한다", async ({ page }) => {
  await page.goto("/");
  await expect(main(page).getByRole("heading", { name: "관리 홈", exact: true })).toBeVisible();
  await expect(main(page).getByText("가상 오류 예시 · 실제 운영 데이터 아님", { exact: true })).toBeVisible();
  await main(page).getByRole("navigation", { name: "관리 화면 선택" }).getByRole("link", { name: "오류 목록", exact: true }).click();
  await search(page, "7F2B91");
  await expect(main(page).getByText("현재 조건 1 / 전체 4개 묶음", { exact: true })).toBeVisible();
  await main(page).getByRole("combobox", { name: "처리 상태", exact: true }).selectOption("new");
  await expect(page).toHaveURL(/status=new/);
  await main(page).getByRole("link", { name: "LLM_TIMEOUT 채팅 분류 LLM 응답 시간 초과" }).click();
  await expect(selectedOccurrence(page).getByRole("heading", { name: /ERR-7F2B91/ })).toBeVisible();
  await expect(selectedOccurrence(page).getByText("tr_01JA9Q2B7T0E", { exact: true })).toBeVisible();
  await page.reload();
  await expect(selectedOccurrence(page).getByRole("heading", { name: /ERR-7F2B91/ })).toBeVisible();
  await main(page).getByRole("link", { name: "← 검색 조건을 유지한 오류 목록", exact: true }).click();
  await expect(main(page).getByLabel("오류 검색", { exact: true })).toHaveValue("7F2B91");
  await expect(main(page).getByRole("combobox", { name: "처리 상태", exact: true })).toHaveValue("new");
  await expect(main(page).getByText("현재 조건 1 / 전체 4개 묶음", { exact: true })).toBeVisible();
});

test("필터는 함께 적용되고 상시 작업에서 발생한 서버 오류도 찾으며 빈 결과를 초기화한다", async ({ page }) => {
  await page.goto("/?view=errors");
  await main(page).getByLabel("오류 검색", { exact: true }).fill("아직 제출하지 않은 검색어");
  await main(page).getByRole("link", { name: "검색·필터 초기화", exact: true }).click();
  await expect(main(page).getByLabel("오류 검색", { exact: true })).toHaveValue("");
  await main(page).getByRole("combobox", { name: "발생 출처", exact: true }).selectOption("job");
  await expect(main(page).getByText("현재 조건 2 / 전체 4개 묶음", { exact: true })).toBeVisible();
  await main(page).getByRole("combobox", { name: "심각도", exact: true }).selectOption("high");
  await expect(page).toHaveURL(/severity=high/);
  await search(page, "job_classifying");
  await main(page).getByRole("link", { name: "LLM_TIMEOUT 채팅 분류 LLM 응답 시간 초과" }).click();
  await expect(selectedOccurrence(page).getByRole("heading", { name: /ERR-7F1D20/ })).toBeVisible();
  await expect(selectedOccurrence(page).getByText("기록 없음 · 상시 작업", { exact: true })).toBeVisible();
  await main(page).getByRole("link", { name: "← 검색 조건을 유지한 오류 목록", exact: true }).click();
  await main(page).getByRole("combobox", { name: "처리 상태", exact: true }).selectOption("resolved");
  await expect(main(page).getByText("조건에 맞는 오류 묶음이 없습니다.", { exact: true })).toBeVisible();
  await main(page).getByRole("link", { name: "검색·필터 초기화", exact: true }).click();
  await expect(main(page).getByText("현재 조건 4 / 전체 4개 묶음", { exact: true })).toBeVisible();
});

test("없는 묶음과 발생은 명시적 오류이며 0명과 상세 미수집을 구분한다", async ({ page }) => {
  await page.goto("/?view=errors&q=missing&incident=unknown");
  await expect(main(page).getByRole("alert")).toContainText("요청한 오류 묶음을 찾을 수 없습니다");
  await expect(main(page).getByRole("heading", { name: "채팅 분류 LLM 응답 시간 초과", exact: true })).toHaveCount(0);
  await main(page).getByRole("link", { name: "검색 조건을 유지한 오류 목록으로 돌아가기", exact: true }).click();
  await expect(main(page).getByLabel("오류 검색", { exact: true })).toHaveValue("missing");

  await page.goto("/?view=errors&incident=fp_llm&occurrence=unknown");
  await expect(main(page).getByRole("alert")).toContainText("요청한 발생 기록을 찾을 수 없습니다");
  await expect(selectedOccurrence(page)).toHaveCount(0);
  await main(page).getByRole("link", { name: /ERR-7F3A2C 14:32:05/ }).click();
  await expect(selectedOccurrence(page).getByRole("heading", { name: /ERR-7F3A2C/ })).toBeVisible();

  await page.goto("/?view=errors&incident=fp_kma");
  await expect(main(page).getByText("0명", { exact: true })).toBeVisible();
  await expect(main(page).getByText("이 묶음에는 발생 상세 예시가 없습니다. 오류가 없다는 뜻은 아닙니다.", { exact: true })).toBeVisible();
  await page.goto("/?view=errors&incident=fp_kma&occurrence=unknown");
  await expect(main(page).getByRole("alert")).toContainText("요청한 발생 기록을 찾을 수 없습니다");
});

test("관리 화면은 320px와 390px에서 넘침 없이 표시되고 기존 시험 도구로 이동한다", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto("/");
  await expect(main(page).getByRole("heading", { name: "관리 홈", exact: true })).toBeVisible();
  await expectNoOverflow(page);
  await page.goto("/?view=errors");
  await expect(main(page).getByText("현재 조건 4 / 전체 4개 묶음", { exact: true })).toBeVisible();
  await expectNoOverflow(page);
  await page.goto("/?view=errors&incident=fp_llm");
  await expect(selectedOccurrence(page)).toBeVisible();
  await expectNoOverflow(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "test-results/dev-management-detail-mobile.png", fullPage: true });
  await page.emulateMedia({ colorScheme: "dark" });
  await expectNoOverflow(page);
  await page.getByRole("navigation", { name: "개발팀 메뉴" }).getByRole("link", { name: "팀별 테스트", exact: true }).click();
  await expect(main(page).getByRole("heading", { name: "에이전트 테스트", exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test("관리 홈·목록·상세의 데스크톱 표시를 검토용으로 저장한다", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await expect(main(page).getByRole("heading", { name: "관리 홈", exact: true })).toBeVisible();
  await page.screenshot({ path: "test-results/dev-management-home.png", fullPage: true });
  await page.goto("/?view=errors");
  await expect(main(page).getByText("현재 조건 4 / 전체 4개 묶음", { exact: true })).toBeVisible();
  await page.screenshot({ path: "test-results/dev-management-errors.png", fullPage: true });
  await page.goto("/?view=errors&incident=fp_llm");
  await expect(selectedOccurrence(page)).toBeVisible();
  await page.screenshot({ path: "test-results/dev-management-detail.png", fullPage: true });
});
