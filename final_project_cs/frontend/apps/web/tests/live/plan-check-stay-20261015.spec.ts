import { expect, test } from "@playwright/test";
import { dayTab, mockServer, noHorizontalScroll, start } from "./helpers";
import { INTAKE } from "./plan-check-kit";

/**
 * `[2026-10-15 ST4F-499]` 계획 확인 화면(등록 전)의 숙소 — mock 서버 장면 `board: "stay"`(`freshStayBoard`): 3일 계획, 1일차 15:00 롯데호텔 서울 체크인(3일차 11:00 체크아웃 — 한 항목),
 * 2일차 · 3일차 아침 「숙소 → 첫 일정」 이동(`from_stay`). 등록 뒤 일정 화면의 같은 표시는 `stay-b-20261013.spec.ts` 가 본다.
 * mock 서버 시험(화면 반응)이다 — 실서버 응답으로 확인한 것이 아니다.
 */
type Page = import("@playwright/test").Page;
const day = (page: Page, n: number) => page.locator(`section[aria-labelledby="plan-day-${n}"]`);
const order = (page: Page, n: number) => day(page, n).locator("[data-entry-id]").evaluateAll((nodes) => nodes.map((node) => node.getAttribute("data-entry-id")));
const SHOTS = process.env.STAY_SHOTS_DIR;
/** The list scrolls inside the sheet — a picture of the day's section alone comes out grey past the fold, so bring the stay into view and take the screen. */
async function shot(page: Page, stay: import("@playwright/test").Locator, date: string) {
  await stay.scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${SHOTS}/plan-stay-${date}.png` });
}

test.beforeEach(async ({ request }) => {
  await mockServer(request).reset();
  await mockServer(request).scenario({ review: "on", board: "stay", readingPolls: 0 });
});

test("체크인 날은 숙소 카드와 박 수, 묵는 날은 맨 위 「숙소에서 출발」 띠 다음에 아침 이동", async ({ page }) => {
  await page.setViewportSize({ width: 430, height: 932 });
  await start(page);
  await page.goto(`/intakes/${INTAKE}`);

  await dayTab(page, /^1일차/).click();                                                    // the day chips show once the check has ended
  const first = day(page, 1);
  // `[2026-10-15 사용자 결정]` The title is the name only, the pill under it 「체크인 · 2박 · 날짜」; the card is still read as one.
  await expect(first.getByRole("article", { name: "롯데호텔 서울 체크인 · 2박 · 10/1~10/3", exact: true })).toBeVisible();
  await expect(first.locator("#plan-item-0-1")).toHaveText("롯데호텔 서울");
  await expect(first.locator("#plan-item-0-1-stay")).toHaveText("체크인 · 2박 · 10/1~10/3");
  expect(await order(page, 1)).toEqual(["0-0", "0-0:0-1", "0-1", "0-1:0-2", "0-2"]);      // the evening leg leaves the hotel on the check-in day; no band on that day
  if (SHOTS) await shot(page, first.locator("#plan-card-0-1"), "2026-10-01");

  await dayTab(page, /^2일차/).click();
  const second = day(page, 2);
  await expect(second.getByText("롯데호텔 서울에서 출발", { exact: true })).toBeVisible();
  await expect(second.getByText("2박째", { exact: true })).toBeVisible();
  expect(await order(page, 2)).toEqual(["0-1:from", "0-1:0-3", "0-3"]);                   // band, then the morning leg, then the day's first stop
  if (SHOTS) await shot(page, second.locator('[data-entry-id="0-1:from"]'), "2026-10-02");

  await dayTab(page, /^3일차/).click();
  const last = day(page, 3);
  await expect(last.getByText("롯데호텔 서울에서 출발", { exact: true })).toBeVisible();
  await expect(last.getByText("마지막 날", { exact: true })).toBeVisible();
  expect(await order(page, 3)).toEqual(["0-1:from", "0-1:0-4", "0-4"]);
  if (SHOTS) await shot(page, last.locator('[data-entry-id="0-1:from"]'), "2026-10-03");
  await noHorizontalScroll(page);

  // `[2026-10-15 사용자 결정]` The band is pressed like the trip screen's: the stay's check-in day, its card marked and open.
  await last.getByRole("button", { name: "롯데호텔 서울에서 출발 — 숙소 보기" }).click();
  await expect(dayTab(page, /^1일차/)).toHaveAttribute("aria-selected", "true");
  await expect(day(page, 1).locator('li[data-entry-id="0-1"]')).toHaveAttribute("data-selected", "true");
  await expect(page.locator("#plan-card-0-1")).toHaveAttribute("data-open", "true");
  await expect(page.locator("#plan-card-0-1")).toBeInViewport();
  await expect(page.locator('p[aria-live="polite"]').filter({ hasText: "\uB86F\uB370\uD638\uD154 \uC11C\uC6B8" })).toContainText("\uC219\uBC15");
});
