import { expect, test, type Page } from "@playwright/test";
import { mockServer } from "./helpers";
import { openFinished, type Json } from "./plan-check-kit";

/**
 * `[2026-10-05 사용자 요청 — 날짜 전환 애니메이션 · 두 손가락 확대]` 계획 확인 화면의 하루씩 보기. mock 서버 시험이다 — 화면 반응만 본다(실기기 손가락 감각은 못 봤다).
 *   - 목록이 손가락을 따라 옆으로 움직이고 옆 날이 함께 밀려 들어온다, 기준선을 넘어야 날이 바뀐다, 모자라면 되돌아간다.
 *   - 날짜 칩 아래의 표시가 손가락과 함께 칩 사이를 미끄러진다.
 *   - 첫날·마지막 날에서는 고무줄처럼 조금만 밀린다.
 *   - 두 손가락을 오므리면 줄어들다가 끝까지 오므리면 전체 일정, 벌리면 하루 보기로 돌아온다.
 */
const DAY_TWO_STOP: Json = {
  id: "0-3", source_id: "s1", index: 3, title: "N서울타워", kind: "activity", day: 2, date: "2026-10-02", starts_at: "10:00", ends_at: "11:30",
  locked: false, status: "keep", can_lock: true, place_state: "found", candidates_hint: null,
  place: { name: "N서울타워", latitude: 37.5512, longitude: 126.9882, source: "tour_api", kind: null, content_id: null, content_type_id: null },
  rows: [{ row: "place", result: "ok", text: "관광공사 정보로 찾았어요" }],
};

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });
test.use({ hasTouch: true });

/** 손가락을 흉내 낸다: 이벤트 하나씩 보내 중간 모습을 볼 수 있다. */
async function finger(page: Page, type: "pointerdown" | "pointermove" | "pointerup", x: number, y: number, id = 7, primary = true) {
  await page.evaluate(([type, x, y, id, primary]) => {
    const target = document.querySelector("div[class*=sheetBody]")!;
    target.dispatchEvent(new PointerEvent(type as string, { bubbles: true, cancelable: true, pointerId: id as number, pointerType: "touch", isPrimary: primary as boolean, clientX: x as number, clientY: y as number, button: 0, buttons: type === "pointerup" ? 0 : 1 }));
  }, [type, x, y, id, primary] as const);
  if (type === "pointermove") await page.waitForTimeout(160);                                         // 사람의 손은 이벤트를 한꺼번에 보내지 않는다 — 너무 빠르면 「휙 쓸기」로 읽힌다
}
const trackShift = (page: Page) => page.evaluate(() => {
  const track = document.querySelector("div[class*=dayTrack]") as HTMLElement | null;
  return track ? new DOMMatrixReadOnly(getComputedStyle(track).transform).m41 : null;
});
const markerLeft = (page: Page) => page.evaluate(() => new DOMMatrixReadOnly(getComputedStyle(document.querySelector("span[class*=dayMarker]")!).transform).m41);
const zoomOf = (page: Page) => page.evaluate(() => Number(getComputedStyle(document.querySelector("div[class*=dayZoom]")!).zoom));
const withDays = (view: Json) => { view.review.items.push(DAY_TWO_STOP); };

test("끄는 동안 목록이 손가락을 따라 움직이고 옆 날이 함께 밀려 들어온다 — 기준선을 못 넘기면 되돌아가고, 넘으면 날이 바뀐다", async ({ page, request }) => {
  await openFinished(page, request, withDays);
  await expect(page.getByRole("tab", { name: /^1일차/ })).toHaveAttribute("aria-selected", "true");
  await finger(page, "pointerdown", 300, 400);
  await finger(page, "pointermove", 270, 402);
  await finger(page, "pointermove", 230, 404);                                                       // 70px 왼쪽으로: 기준선 앞
  expect(await trackShift(page)).toBeCloseTo(-70, 0);                                                // 손가락 그대로 따라온다
  await expect(page.locator("div[class*=peek]")).toHaveCount(1);                                     // 옆 날(2일차)이 함께 있다
  await expect(page.locator("div[class*=peek]")).toContainText("N서울타워");
  await expect(page.locator("div[class*=dayTrack]")).not.toHaveAttribute("data-armed", "");           // 아직 기준선 앞
  await finger(page, "pointerup", 230, 404);                                                         // 놓으면 되돌아간다
  await expect.poll(() => trackShift(page), { timeout: 3000 }).toBe(0);
  await expect(page.getByRole("tab", { name: /^1일차/ })).toHaveAttribute("aria-selected", "true");   // 날은 안 바뀌었다
  await expect(page.locator("div[class*=peek]")).toHaveCount(0);

  await finger(page, "pointerdown", 330, 400);
  await finger(page, "pointermove", 280, 402);
  await finger(page, "pointermove", 200, 404);                                                       // 130px: 기준선(폭의 28%)을 넘었다
  await expect(page.locator("div[class*=dayTrack]")).toHaveAttribute("data-armed", "");
  await expect(page.locator("span[class*=peekBadge]")).toContainText("놓으면 2일차");
  await finger(page, "pointerup", 200, 404);
  await expect(page.getByRole("tab", { name: /^2일차/ })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("article", { name: "N서울타워", exact: true })).toBeVisible();
  await expect.poll(() => trackShift(page), { timeout: 3000 }).toBe(0);                              // 목록이 제자리로 돌아와 있다(밀린 채 남지 않는다)
});

test("날짜 칩 아래의 표시가 손가락과 함께 다음 칩 쪽으로 미끄러지고, 날이 바뀌면 그 칩 위에 선다", async ({ page, request }) => {
  await openFinished(page, request, withDays);
  const before = await markerLeft(page);
  await finger(page, "pointerdown", 330, 400);
  await finger(page, "pointermove", 300, 402);
  await finger(page, "pointermove", 240, 404);
  const during = await markerLeft(page);
  expect(during).toBeGreaterThan(before);                                                            // 다음 칩(오른쪽)으로 움직이는 중
  await finger(page, "pointermove", 200, 404);                                                       // 기준선을 넘도록 더 민다
  await finger(page, "pointerup", 200, 404);
  await expect(page.getByRole("tab", { name: /^2일차/ })).toHaveAttribute("aria-selected", "true");
  await expect.poll(async () => {
    const tab = await page.getByRole("tab", { name: /^2일차/ }).boundingBox();
    const marker = await page.locator("span[class*=dayMarker]").boundingBox();
    return Math.abs(tab!.x - marker!.x);
  }, { timeout: 3000 }).toBeLessThan(2);                                                             // 표시가 2일차 칩 위에 있다
  await expect(page.getByRole("tab", { name: /^2일차/ })).toHaveAttribute("data-lit", "");
});

test("마지막 날에서 더 밀면 고무줄처럼 조금만 밀리고 「마지막 날이에요」가 보이며, 놓으면 제자리로 돌아온다", async ({ page, request }) => {
  await openFinished(page, request, withDays);
  await page.getByRole("tab", { name: /^2일차/ }).click();
  await expect(page.getByRole("tab", { name: /^2일차/ })).toHaveAttribute("aria-selected", "true");
  await finger(page, "pointerdown", 330, 400);
  await finger(page, "pointermove", 280, 402);
  await finger(page, "pointermove", 130, 404);                                                       // 200px 밀었다
  const shift = (await trackShift(page))!;
  expect(shift).toBeLessThan(-20);
  expect(shift).toBeGreaterThan(-90);                                                                // 고무줄: 손가락 길이보다 훨씬 짧다
  await expect(page.getByText("마지막 날이에요")).toBeVisible();
  await finger(page, "pointerup", 130, 404);
  await expect(page.getByRole("tab", { name: /^2일차/ })).toHaveAttribute("aria-selected", "true");   // 날은 그대로
  await expect.poll(() => trackShift(page), { timeout: 3000 }).toBe(0);
  await expect(page.getByText("마지막 날이에요")).toHaveCount(0);
});

test("두 손가락으로 오므리면 줄어들다가 끝까지 오므리면 전체 일정으로, 벌리면 하루 보기로 돌아온다", async ({ page, request }) => {
  await openFinished(page, request, withDays);
  await finger(page, "pointerdown", 150, 420, 1);
  await finger(page, "pointerdown", 250, 420, 2, false);                                             // 두 손가락 100px
  await finger(page, "pointermove", 175, 420, 1);
  await finger(page, "pointermove", 225, 420, 2);                                                    // 50px 로 오므림 → 절반 크기(아래쪽 한계 0.55)
  expect(await zoomOf(page)).toBeCloseTo(0.55, 1);
  await finger(page, "pointerup", 175, 420, 1);
  await finger(page, "pointerup", 225, 420, 2);                                                      // 끝까지 오므리고 놓음
  await expect(page.getByRole("tab", { name: "전체" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("article", { name: "경복궁 관람", exact: true })).toBeVisible();
  await expect(page.getByRole("article", { name: "N서울타워", exact: true })).toBeVisible();          // 두 날이 이어진 개요

  await finger(page, "pointerdown", 190, 420, 1);
  await finger(page, "pointerdown", 210, 420, 2, false);
  await finger(page, "pointermove", 100, 420, 1);
  await finger(page, "pointermove", 300, 420, 2);                                                    // 크게 벌림 → 한계까지
  await finger(page, "pointerup", 100, 420, 1);
  await finger(page, "pointerup", 300, 420, 2);
  await expect(page.getByRole("tab", { name: /^1일차/ })).toHaveAttribute("aria-selected", "true");   // 하루 보기로 돌아왔다
});

test("조금만 오므리거나 벌리면 목록 크기만 바뀌고(범위 안) 날 보기는 그대로이며, 크기는 기억된다", async ({ page, request }) => {
  await openFinished(page, request, withDays);
  await finger(page, "pointerdown", 140, 420, 1);
  await finger(page, "pointerdown", 260, 420, 2, false);                                             // 120px
  await finger(page, "pointermove", 130, 420, 1);
  await finger(page, "pointermove", 290, 420, 2);                                                    // 160px → 약 1.33 배 → 한계 1.3 으로
  await finger(page, "pointerup", 130, 420, 1);
  await finger(page, "pointerup", 290, 420, 2);
  await expect(page.getByRole("tab", { name: /^1일차/ })).toHaveAttribute("aria-selected", "true");   // 하루 보기 그대로
  await expect.poll(() => zoomOf(page)).toBeCloseTo(1.3, 1);
  expect(await page.evaluate(() => window.localStorage.getItem("triPilot.planListZoom"))).toBe("1.3");
  await page.reload();
  await expect(page.getByRole("tab", { name: /^1일차/ })).toBeVisible();
  await expect.poll(() => zoomOf(page)).toBeCloseTo(1.3, 1);                                         // 다시 열어도 같은 크기
});
