import { expect, test, type Page } from "@playwright/test";
import { dayTab, mockServer, openPane, start, STUB, TRIP_ID, tripScreen } from "./helpers";
import { INTAKE } from "./plan-check-kit";

/**
 * `[2026-10-22 사용자 결정 — ST4F-718]` The view the trip screen opens on, and the last stop ending while it is open. The mock server's trip runs 2026-10-01 08:00 → 2026-10-02 11:30
 * (its last stop 「둘째 날 박물관」 10:00–11:30). The page's clock is set (and left running, like `beforeTheTrip`) at the moment each case needs.
 */
async function at(page: Page, time: string) {
  await page.clock.install({ time: new Date(`${time}+09:00`) });
  await page.clock.resume();
}

async function openTrip(page: Page) {
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(tripScreen(page)).toBeVisible();
}

const endCard = (page: Page) => tripScreen(page).getByRole("article").filter({ hasText: "여행이 끝났어요" });
const credits = (page: Page) => page.getByRole("dialog", { name: /엔딩 크레딧/ });

test.beforeEach(async ({ page, request }) => {
  await mockServer(request).reset();
  await start(page);
});

test("시작 전(1일차 날짜 전)에는 「전체」로 열리고 결산 카드는 없다", async ({ page }) => {
  await at(page, "2026-09-30T12:00:00");
  await openTrip(page);
  await expect(dayTab(page, /^전체/)).toHaveAttribute("aria-selected", "true");
  await expect(tripScreen(page).getByText("아침 식당", { exact: true }).first()).toBeVisible();
  await expect(tripScreen(page).getByText("둘째 날 박물관", { exact: true }).first()).toBeVisible();
  await expect(endCard(page)).toHaveCount(0);
});

test("여행 중에는 지금처럼 오늘 일차로 열린다 — 1일차 날 첫 일정 전에도 1일차", async ({ page }) => {
  await at(page, "2026-10-01T06:00:00");
  await openTrip(page);
  await expect(dayTab(page, /^1일차/)).toHaveAttribute("aria-selected", "true");
  await expect(tripScreen(page).getByText("둘째 날 박물관", { exact: true })).toHaveCount(0);
});

test("마지막 일정이 끝난 뒤에는 「전체」 맨 위 결산 카드로 열리고, 크레딧은 저절로 열리지 않는다", async ({ page }) => {
  await at(page, "2026-10-03T09:00:00");
  await openTrip(page);
  await expect(dayTab(page, /^전체/)).toHaveAttribute("aria-selected", "true");
  await expect(endCard(page)).toBeVisible();
  await expect(endCard(page).getByRole("button", { name: "엔딩 크레딧 보기" })).toBeVisible();
  await expect(credits(page)).toHaveCount(0);
});

test("일정 칸을 보는 중 마지막 일정이 끝나면 「전체」로 바뀌고 엔딩 크레딧이 한 번 저절로 열린다", async ({ page }) => {
  await at(page, "2026-10-02T11:28:30");
  await openTrip(page);
  await expect(dayTab(page, /^2일차/)).toHaveAttribute("aria-selected", "true");
  await expect(credits(page)).toHaveCount(0);
  await page.clock.fastForward("03:00");
  await expect(credits(page)).toBeVisible();
  await expect(dayTab(page, /^전체/)).toHaveAttribute("aria-selected", "true");
  await page.getByRole("button", { name: "건너뛰기" }).click();
  await page.getByRole("button", { name: "닫기", exact: true }).click();
  await expect(endCard(page)).toBeVisible();
  // Opened again after the end: the end card, not the credits again (they started once on this device).
  await page.reload();
  await expect(tripScreen(page)).toBeVisible();
  await expect(endCard(page)).toBeVisible();
  await expect(credits(page)).toHaveCount(0);
});

test("채팅 칸을 보는 중 끝나면 크레딧은 열리지 않고, 일정 칸으로 돌아오면 「전체」 결산 카드가 있다", async ({ page }) => {
  await at(page, "2026-10-02T11:28:30");
  await openTrip(page);
  await openPane(page, "채팅");
  await page.clock.fastForward("03:00");
  await page.waitForTimeout(1_500);
  await expect(credits(page)).toHaveCount(0);
  await openPane(page, "일정");
  await expect(dayTab(page, /^전체/)).toHaveAttribute("aria-selected", "true");
  await expect(endCard(page)).toBeVisible();
});

test("수정 모드에서 돌아오면 보던 일차 그대로다(D5)", async ({ page, request }) => {
  await mockServer(request).scenario({ review: "on", board: "rich", readingPolls: 0, routeShapes: "on" });
  // The mock server has no `POST …/reopen` · `…/cancel`: answer them like `trip-edit-opening-20261017.spec.ts` does.
  const response = await request.get(`${STUB}/v1/web/trip-intakes/${INTAKE}`, { headers: { "X-User-Key": "acop_u_known" } });
  const view = await response.json();
  view.reopen = { trip_id: TRIP_ID, version: 1, frozen_item_ids: [], frozen: [] };
  await page.route(`**/v1/web/trips/${TRIP_ID}/reopen`, (route) => route.fulfill({ json: view }));
  await page.route(`**/v1/web/trip-intakes/${INTAKE}/cancel`, (route) => route.fulfill({ json: { intake_id: INTAKE, status: "closed" } }));
  await at(page, "2026-10-01T06:00:00");
  await openTrip(page);
  await dayTab(page, /^2일차/).click();
  await expect(dayTab(page, /^2일차/)).toHaveAttribute("aria-selected", "true");
  await page.getByRole("button", { name: "일정 수정", exact: true }).click();
  await page.getByRole("button", { name: "취소", exact: true }).click();
  await page.getByRole("button", { name: "변경 취소", exact: true }).click();
  await expect(tripScreen(page)).toBeVisible();
  await expect(dayTab(page, /^2일차/)).toHaveAttribute("aria-selected", "true");
});
