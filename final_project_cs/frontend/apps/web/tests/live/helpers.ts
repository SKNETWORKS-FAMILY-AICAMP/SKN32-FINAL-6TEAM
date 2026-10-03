import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const STUB = `http://127.0.0.1:${process.env.STUB_PORT ?? 8043}`;
/** The web app under test (`tests/live/serve.mjs`). */
export const APP = `http://127.0.0.1:${process.env.LIVE_PORT ?? 3102}`;
export const TRIP_ID = "11111111-2222-3333-4444-555555555555";
export const KEY_STORAGE = "tripilot.web.user-key.v1";

export interface LoggedRequest { method: string; path: string; key: string | null; accept: string | null; body: Record<string, unknown> | null }

/** Talks to the test mock server's test control (never part of the real API). */
export function mockServer(request: APIRequestContext) {
  return {
    reset: async () => { await request.post(`${STUB}/__test/reset`); },
    scenario: async (change: Record<string, unknown>) => { await request.post(`${STUB}/__test/scenario`, { data: change }); },
    log: async (): Promise<LoggedRequest[]> => (await request.get(`${STUB}/__test/log`)).json(),
    /** Ring the "this trip changed" bell on every open stream; returns how many streams were open. */
    ring: async (kinds?: string[]): Promise<number> => (await (await request.post(`${STUB}/__test/ring`, { data: kinds ? { kinds } : {} })).json()).rang,
    /** Close every open bell stream, as a dropped connection would. */
    hangup: async (): Promise<number> => (await (await request.post(`${STUB}/__test/hangup`)).json()).closed,
    /** Requests received for a path (matched by suffix), oldest first. */
    async received(method: string, suffix: string): Promise<LoggedRequest[]> {
      return (await this.log()).filter((entry) => entry.method === method && entry.path.endsWith(suffix));
    },
  };
}

/** Korean UI, and a stored user key the test mock server knows (unless `key` is null: a first visit). */
export async function start(page: Page, key: string | null = "acop_u_known") {
  await page.addInitScript(([storageKey, value]) => {
    if (!localStorage.getItem("tripilot.web.settings.v1")) localStorage.setItem("tripilot.web.settings.v1", JSON.stringify({ language: "ko", navigation: "fixed" }));
    if (value && !localStorage.getItem(storageKey)) localStorage.setItem(storageKey, value);
  }, [KEY_STORAGE, key] as const);
}

/** Finish the onboarding: agree to the terms, skip every question but the last, answer that one. Leaves the summary open. */
export async function finishOnboarding(page: Page, beforeTerms?: () => Promise<void>) {
  await page.goto("/start");
  await beforeTerms?.();
  await page.getByRole("button", { name: /약관 동의/ }).click();
  await page.getByRole("button", { name: /전체 약관 읽기/ }).click();
  const reader = page.getByRole("dialog", { name: "서비스 이용 및 개인정보 안내" });
  await reader.getByRole("article").evaluate((element) => { element.scrollTop = element.scrollHeight; });
  await reader.getByText(/^\[필수\]/).click();
  await page.getByRole("button", { name: "동의하고 다음으로" }).click();
  await page.getByRole("button", { name: "시작하기" }).click();
  await expect(page.locator("#question-title-0")).toBeFocused();   // 「시작하기」의 넘김이 끝나야 다음 누름을 받는다
  const skip = page.getByRole("button", { name: "응답하지 않고 넘어가기" });
  // ★카드가 넘어가는 동안의 누름은 화면이 무시한다 — 넘김이 끝나 다음 카드 제목으로 초점이 옮겨진 것을 보고 다음을 누른다
  for (let index = 0; index < 5; index += 1) {
    await skip.click();
    await expect(page.locator(`#question-title-${index + 1}`)).toBeFocused();
  }
  await page.getByRole("button", { name: "여유롭게" }).click();
  await page.getByRole("button", { name: "설정 완료" }).click();
  await expect(page.getByRole("heading", { name: "여행 취향 설정 완료" })).toBeVisible();
}

/** Open the registration page once React has taken it over (a field filled before that is lost). */
export async function openRegistration(page: Page) {
  await page.goto("/trips/new");
  await expect(page.locator("#plan-source")).toBeVisible();
  await page.waitForFunction(() => {
    const element = document.querySelector("textarea");
    return Boolean(element) && Object.keys(element as object).some((key) => key.startsWith("__reactFiber"));
  });
}

/** The registration page's three panels (live): by the heading each shows. */
export const PANES = {
  text: (page: Page) => page.getByRole("region", { name: "직접 입력" }),
  files: (page: Page) => page.getByRole("region", { name: "파일 선택", exact: true }),
  plan: (page: Page) => page.getByRole("region", { name: "계획 짜 주기 (테스트)" }),
};

/** Fill the third panel, 「계획 짜 주기 (테스트)」: first day, days, travelers and (optionally) the wish. */
export async function fillPlanAsk(page: Page, ask: { start: string; days: number; party: number; wish?: string }) {
  await page.getByLabel("첫날", { exact: true }).fill(ask.start);
  await page.getByLabel("일수", { exact: true }).selectOption(String(ask.days));
  await page.getByLabel("인원", { exact: true }).selectOption(String(ask.party));
  if (ask.wish !== undefined) await page.getByLabel("원하는 여행", { exact: false }).fill(ask.wish);
}

/** A first day that is surely not past: a week from today in Seoul. */
export function weekAhead(): string {
  return new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toLocaleDateString("sv-SE", { timeZone: "Asia/Seoul" });
}

// ── helpers that came from the old demo-build suite (`tests/e2e`, removed 2026-10-03) ─────────────────────────

/** Korean UI and no stored key: a first visit, which asks the test mock server for nothing until the customer registers. */
export const useKorean = (page: Page) => start(page, null);

/**
 * Next draws a page on the server first, and a click before React has taken it over does nothing. Wait until the element is React's
 * (found 2026-10-03: a press did nothing when the machine was busy).
 */
export async function hydrated(page: Page, selector = "textarea") {
  await page.waitForFunction((css) => {
    const element = document.querySelector(css);
    return Boolean(element) && Object.keys(element as object).some((key) => key.startsWith("__reactFiber"));
  }, selector);
}

export async function noHorizontalScroll(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
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

/** The start screen is asked once and kept in this browser. For a test that needs the first-time screen again: forget what it kept, then reload. */
export async function forgetStartScreen(page: Page) {
  await page.evaluate(() => localStorage.removeItem("tripilot.web.onboarding.v1"));
  await page.reload();
}

/**
 * Open the start screen's preferences from My page (menu → My page → the preferences card's 수정). Done inside the app, so the page-only
 * state (the active trip) stays. ★The intro button no longer leads here once the terms are agreed.
 */
export async function openPreferencesFromMyPage(page: Page) {
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await page.getByRole("dialog", { name: "메뉴" }).getByRole("link", { name: /마이페이지/ }).click();
  await expect(page).toHaveURL(/\/mypage$/);
  await page.locator("section").filter({ has: page.getByRole("heading", { name: "여행 취향", exact: true }) }).getByRole("button", { name: "수정", exact: true }).click();
  await expect(page).toHaveURL(/\/start$/);
}

/**
 * Register a trip the way a customer does, against the test mock server: write a plan, 「계획 확인하기」, wait for the plan-check screen's result,
 * 「여행 등록」, and land on the trip screen (the mock's one trip, `TRIP_ID`). Needs the mock's default scenario (a plan whose check passes).
 */
export async function registerStubTrip(page: Page, plan = "10/1 09:00 경복궁 관람") {
  await openRegistration(page);
  await page.getByLabel("나의 여행 계획").fill(plan);
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);
  await page.getByRole("button", { name: "여행 등록" }).click();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));
  await expect(page.getByRole("heading", { name: "나의 여행", exact: true })).toBeVisible();
}
