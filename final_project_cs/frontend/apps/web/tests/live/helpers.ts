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
