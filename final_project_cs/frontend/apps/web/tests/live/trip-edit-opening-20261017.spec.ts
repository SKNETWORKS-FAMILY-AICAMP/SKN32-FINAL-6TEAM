import { expect, test } from "@playwright/test";
import { beforeTheTrip, mockServer, start, STUB, TRIP_ID, tripScreen } from "./helpers";
import { INTAKE } from "./plan-check-kit";

test.beforeEach(async ({ page, request }) => {
  await mockServer(request).reset();
  await mockServer(request).scenario({ review: "on", board: "rich", readingPolls: 0, routeShapes: "on" });
  await start(page);
  await beforeTheTrip(page);
});

for (const width of [375, 1280]) test(`${width}px: 수정 접수 응답 전에도 저장된 여행이 즉시 보이고 변경은 막힌다`, async ({ page, request }) => {
  await page.setViewportSize({ width, height: 812 });
  const response = await request.get(`${STUB}/v1/web/trip-intakes/${INTAKE}`, { headers: { "X-User-Key": "acop_u_known" } });
  const view = await response.json();
  view.reopen = { trip_id: TRIP_ID, version: 1, frozen_item_ids: [], frozen: [] };
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route(`**/v1/web/trips/${TRIP_ID}/reopen`, async (route) => { await gate; await route.fulfill({ json: view }); });
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(tripScreen(page)).toBeVisible();
  await page.getByRole("button", { name: "일정 수정", exact: true }).click();
  await expect(page.getByRole("button", { name: "취소", exact: true })).toBeVisible({ timeout: 1000 });
  await expect(page.getByRole("status").filter({ hasText: "수정할 일정을 준비하고 있어요…" })).toBeVisible({ timeout: 1000 });
  await expect(page.locator("#plan-card-i-a")).toContainText("아침 식당");
  await expect(page.getByRole("button", { name: "아침 식당 수정", exact: true })).toBeDisabled();
  expect((await mockServer(request).log()).filter((r) => /\/(edits|confirm)$/.test(r.path))).toEqual([]);
  await expect(page.getByRole("button", { name: "저장", exact: true })).toHaveCount(0);
  release();
  await expect(page.getByRole("status").filter({ hasText: "수정할 일정을 준비하고 있어요…" })).toHaveCount(0);
  await expect(page.locator("#plan-card-0-0")).toBeVisible();
});

test("준비 중 취소도 늦게 만들어진 수정 접수를 닫고 원래 여행으로 돌아간다", async ({ page, request }) => {
  const response = await request.get(`${STUB}/v1/web/trip-intakes/${INTAKE}`, { headers: { "X-User-Key": "acop_u_known" } });
  const view = await response.json();
  view.reopen = { trip_id: TRIP_ID, version: 1, frozen_item_ids: [], frozen: [] };
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route(`**/v1/web/trips/${TRIP_ID}/reopen`, async (route) => { await gate; await route.fulfill({ json: view }); });
  let cancelled = false;
  await page.route(`**/v1/web/trip-intakes/${INTAKE}/cancel`, async (route) => { cancelled = true; await route.fulfill({ json: { intake_id: INTAKE, status: "closed" } }); });
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(tripScreen(page)).toBeVisible();
  await page.getByRole("button", { name: "일정 수정", exact: true }).click();
  await page.getByRole("button", { name: "취소", exact: true }).click();
  await page.getByRole("button", { name: "변경 취소", exact: true }).click();
  expect(cancelled).toBe(false);
  release();
  await expect(tripScreen(page)).toBeVisible();
  expect(cancelled).toBe(true);
});
