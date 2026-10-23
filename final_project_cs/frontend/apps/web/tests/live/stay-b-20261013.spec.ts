import { expect, test } from "@playwright/test";
import { mockServer, noHorizontalScroll, start, TRIP_ID, tripScreen } from "./helpers";

/**
 * `[2026-10-13 사용자 결정 — 숙소 항목 B안]` 숙소 한 항목 = 한 숙박(체크인 ~ 체크아웃). mock 서버 장면 `tripItems: "stay"` — 4일 여행:
 * 1일차 15:00 롯데호텔 서울 체크인(4일차 11:00 체크아웃 · 한 항목), 2일차 · 4일차 아침 「숙소 → 첫 일정」 이동(`from_stay`), 3일차는 일정 없음.
 */
type Page = import("@playwright/test").Page;
const day = (page: Page, date: string) => page.locator(`section[aria-labelledby="trip-day-${date}"]`);
/** The trip screen shows one day at a time — its tab first. */
async function openDay(page: Page, n: number, date: string) {
  await page.getByRole("tab", { name: new RegExp(`^${n}일차`) }).click();
  await expect(day(page, date)).toBeVisible();
  return day(page, date);
}
const SHOTS = process.env.STAY_SHOTS_DIR;

test.describe("숙소 항목 B안 — 여행 화면", () => {
  test.beforeEach(async ({ request }) => {
    await mockServer(request).reset();
    await mockServer(request).scenario({ tripItems: "stay" });
  });

  test("체크인 날은 숙소 카드, 묵는 날은 「숙소에서 출발」 띠와 아침 이동, 체크아웃 날은 체크아웃 줄", async ({ page }) => {
    await page.setViewportSize({ width: 430, height: 932 });
    await start(page);
    await page.goto(`/trips/${TRIP_ID}`);
    await expect(tripScreen(page)).toBeVisible();

    const first = await openDay(page, 1, "2026-10-01");
    // `[2026-10-15 사용자 결정]` The title is the name only; 「체크인」 leads the nights' line (the card's second line, or the right of a past line).
    await expect(first.getByText("롯데호텔 서울", { exact: true })).toBeVisible();
    await expect(first.getByText("체크인 · 3박 · 10/1~10/4", { exact: true })).toBeVisible();

    if (SHOTS) await first.screenshot({ path: `${SHOTS}/stay-2026-10-01.png` });
    const second = await openDay(page, 2, "2026-10-02");
    await expect(second.getByRole("button", { name: "롯데호텔 서울에서 출발 — 숙소 보기" })).toBeVisible();
    await expect(second.getByText("2박째", { exact: true })).toBeVisible();
    await expect(second.locator('[data-entry-id="s7"]')).toBeVisible();                       // 띠 바로 아래 아침 이동(숙소 → 남산)
    const order = await second.locator("[data-entry-id]").evaluateAll((nodes) => nodes.map((node) => node.getAttribute("data-entry-id")));
    expect(order).toEqual(["s4:from", "s7", "s8"]);

    if (SHOTS) await second.screenshot({ path: `${SHOTS}/stay-2026-10-02.png` });
    const third = await openDay(page, 3, "2026-10-03");
    await expect(third.getByText("3박째", { exact: true })).toBeVisible();                 // 일정이 없는 날도 숙소에서 출발한다

    if (SHOTS) await third.screenshot({ path: `${SHOTS}/stay-2026-10-03.png` });
    const last = await openDay(page, 4, "2026-10-04");
    await expect(last.getByText("마지막 날", { exact: true })).toBeVisible();
    const checkout = last.locator('[data-entry-id="s4:checkout"]');
    await expect(checkout.locator("strong")).toHaveText("롯데호텔 서울");                       // the name, and under it 「체크아웃 · n박 · 날짜」 as on the check-in card
    await expect(checkout.getByText("체크아웃 · 3박 · 10/1~10/4", { exact: true })).toBeVisible();
    const lastOrder = await last.locator("[data-entry-id]").evaluateAll((nodes) => nodes.map((node) => node.getAttribute("data-entry-id")));
    expect(lastOrder.indexOf("s4:checkout")).toBeGreaterThan(lastOrder.indexOf("s10"));    // 09:30 광장시장 뒤, 13:00 창덕궁 앞
    expect(lastOrder.indexOf("s4:checkout")).toBeLessThan(lastOrder.indexOf("s11"));
    if (SHOTS) await last.screenshot({ path: `${SHOTS}/stay-2026-10-04.png` });
    await noHorizontalScroll(page);
  });
});
