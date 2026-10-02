import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const STUB = "http://127.0.0.1:8043";
export const TRIP_ID = "11111111-2222-3333-4444-555555555555";
export const KEY_STORAGE = "tripilot.web.user-key.v1";

export interface LoggedRequest { method: string; path: string; key: string | null; body: Record<string, unknown> | null }

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
