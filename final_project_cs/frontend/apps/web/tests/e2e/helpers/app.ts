import { expect, type Page } from "@playwright/test";

/** Start in Korean unless the test already changed the settings in this browser. */
export async function useKorean(page: Page) {
  await page.addInitScript(() => {
    if (!localStorage.getItem("tripilot.web.settings.v1")) localStorage.setItem("tripilot.web.settings.v1", JSON.stringify({ language: "ko", navigation: "fixed" }));
  });
}

export async function submitPlan(page: Page) {
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page).toHaveURL(/\/trips\/[^/]+\/verification$/);
}

/** Wait for the demo check, then open the results by the user's own action. */
export async function openCompletedResults(page: Page) {
  await expect(page.getByRole("progressbar", { name: "계획 확인 진행률" })).toHaveAttribute("aria-valuenow", "100");
  await expect(page).toHaveURL(/\/verification$/);
  await page.getByRole("link", { name: "결과 확인하기" }).click();
  await expect(page).toHaveURL(/\/results$/);
}

export async function startTrip(page: Page) {
  const start = page.getByRole("button", { name: "여행 관리 시작" });
  await expect(start).toBeDisabled();
  await page.getByRole("checkbox").check();
  await start.click();
  await expect(page).toHaveURL(/\/trips\/[0-9a-f-]+$/);
  await expect(page.getByRole("heading", { name: "나의 여행", exact: true })).toBeVisible();
}

export async function registerExampleTrip(page: Page) {
  await page.goto("/trips/new");
  await page.getByRole("button", { name: "예시 불러오기" }).click();
  const source = await page.getByLabel("나의 여행 계획").inputValue();
  await submitPlan(page);
  await openCompletedResults(page);
  await startTrip(page);
  return { source, tripId: new URL(page.url()).pathname.split("/")[2] };
}

export async function noHorizontalScroll(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
}
