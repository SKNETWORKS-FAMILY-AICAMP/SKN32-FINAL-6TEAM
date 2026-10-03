import { expect, type Page } from "@playwright/test";

/** Start in Korean unless the test already changed the settings in this browser. */
export async function useKorean(page: Page) {
  await page.addInitScript(() => {
    if (!localStorage.getItem("tripilot.web.settings.v1")) localStorage.setItem("tripilot.web.settings.v1", JSON.stringify({ language: "ko", navigation: "fixed" }));
  });
}

/**
 * Next draws the form on the server first, and a click before React has taken the page over does nothing (found 2026-10-03:
 * the example was not loaded, or 「계획 확인하기」 did not move on, when the machine was busy). Wait until the textarea is React's.
 */
export async function hydrated(page: Page, selector = "textarea") {
  await page.waitForFunction((css) => {
    const element = document.querySelector(css);
    return Boolean(element) && Object.keys(element as object).some((key) => key.startsWith("__reactFiber"));
  }, selector);
}

/**
 * Press 「예시 불러오기」 once the page is React's, and wait until the example text is in. ★The example is fetched, so the box fills a
 * moment AFTER the press: pressing 「계획 확인하기」 in that moment sends an empty plan (the page refuses, then clears its message when
 * the text lands — it looked like a press that did nothing; found 2026-10-03 as a different test failing in each full run).
 */
export async function loadExample(page: Page) {
  await hydrated(page);
  await page.getByRole("button", { name: "예시 불러오기" }).click();
  await expect(page.locator("#plan-source")).not.toHaveValue("");
}

export async function submitPlan(page: Page) {
  await hydrated(page);
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
  await loadExample(page);
  const source = await page.getByLabel("나의 여행 계획").inputValue();
  await submitPlan(page);
  await openCompletedResults(page);
  await startTrip(page);
  return { source, tripId: new URL(page.url()).pathname.split("/")[2] };
}

/** Terms card open on /start: read the full terms, agree, go on to the preferences. */
export async function agreeTerms(page: Page) {
  await expect(page.getByRole("button", { name: /약관 동의/ })).toHaveAttribute("aria-expanded", "true");
  await page.getByRole("button", { name: /전체 약관 읽기/ }).click();
  const reader = page.getByRole("dialog", { name: "서비스 이용 및 개인정보 안내" });
  await reader.getByRole("article").evaluate((element) => { element.scrollTop = element.scrollHeight; });
  await reader.getByText(/^\[필수\]/).click();
  await page.getByRole("button", { name: "동의하고 다음으로" }).click();
}

/** In the open menu, unfolds the language card and picks a language by its own name. */
export async function pickMenuLanguage(page: Page, menu: "메뉴" | "Menu", language: "한국어" | "English") {
  const dialog = page.getByRole("dialog", { name: menu });
  await dialog.getByRole("button", { name: /LANGUAGE/ }).click();
  await dialog.getByRole("button", { name: language, exact: true }).click();
}

export async function noHorizontalScroll(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
}

/**
 * `[2026-10-01]` The start screen is asked once and kept in this browser. For a test that needs the first-time screen
 * again: forget what it kept, then reload.
 */
export async function forgetStartScreen(page: Page) {
  await page.evaluate(() => localStorage.removeItem("tripilot.web.onboarding.v1"));
  await page.reload();
}

/**
 * Open the start screen's preferences from My page (menu → My page → the preferences card's 수정). Done inside the app,
 * so the page-only state (the active trip) stays. ★The intro button no longer leads here once the terms are agreed.
 */
export async function openPreferencesFromMyPage(page: Page) {
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await page.getByRole("dialog", { name: "메뉴" }).getByRole("link", { name: /마이페이지/ }).click();
  await expect(page).toHaveURL(/\/mypage$/);
  await page.locator("section").filter({ has: page.getByRole("heading", { name: "여행 취향", exact: true }) }).getByRole("button", { name: "수정", exact: true }).click();
  await expect(page).toHaveURL(/\/start$/);
}
