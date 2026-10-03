import { expect, test } from "@playwright/test";
import { hydrated, mockServer, noHorizontalScroll, openRegistration, useKorean } from "./helpers";

test.beforeEach(async ({ page, request }) => { await mockServer(request).reset(); await useKorean(page); });

// The registration page's three panels, 「계획 확인하기」 being off while the chosen one is empty, what is sent and how a refusal comes back are
// in `registration-panels.spec.ts`, `flow.spec.ts` and `intake-start.spec.ts`. These two keep what only the old demo suite held.

test("작성 중인 계획은 화면을 오가도·새로고침해도 보존되고, 「이전」은 시작 화면(약관 전)으로 간다", async ({ page }) => {
  await openRegistration(page);
  const plan = page.getByLabel("나의 여행 계획");
  const valid = "1일차 · 2026-10-03\n09:00 호텔 조식\n13:00 점심 식당 · 예약 있음";
  await plan.fill(valid);
  await page.locator("form").getByRole("link", { name: "이전", exact: true }).click();
  await expect(page).toHaveURL(/\/start$/);
  await page.goBack();
  await expect(plan).toHaveValue(valid);
  await page.reload();
  await expect(plan).toHaveValue(valid);
  // Nothing was sent to the server for a draft: only 「계획 확인하기」 sends.
  const log = await mockServer(page.request).log();
  expect(log.filter((entry) => entry.method === "POST")).toEqual([]);
});

test("「예시 불러오기」는 글칸에 일주일 뒤부터의 서울 이틀 일정을 채울 뿐이다 — 서버에는 아무것도 가지 않고, 고칠 수 있다", async ({ page, request }) => {
  await openRegistration(page);
  await page.getByRole("button", { name: "예시 불러오기" }).click();
  const plan = page.getByLabel("나의 여행 계획");
  await expect(plan).toHaveValue(/1일차 · \d{4}-\d{2}-\d{2}[\s\S]*2일차 · \d{4}-\d{2}-\d{2}/);
  const text = await plan.inputValue();
  const firstDay = /1일차 · (\d{4}-\d{2}-\d{2})/.exec(text)![1];
  const today = new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Seoul" });
  expect(firstDay > today).toBe(true);                                         // never a past date
  await plan.fill(`${text}\n21:00 숙소 휴식`);
  await expect(plan).toHaveValue(/21:00 숙소 휴식$/);
  expect((await mockServer(request).log()).filter((entry) => entry.method === "POST")).toEqual([]);
  await expect(page.getByText(/데모|시연|Demo/)).toHaveCount(0);
});

test("320px에서 홈과 등록 화면이 가로로 넘치지 않는다", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 720 });
  await page.goto("/");
  await noHorizontalScroll(page);
  await page.getByRole("button", { name: "3. 일정 시작" }).click();
  await page.getByRole("button", { name: "내 일정 시작하기" }).click();
  await expect(page).toHaveURL(/\/start$/);
  await noHorizontalScroll(page);
  await openRegistration(page);
  await page.getByRole("button", { name: "예시 불러오기" }).click();
  await hydrated(page);
  await noHorizontalScroll(page);
});
