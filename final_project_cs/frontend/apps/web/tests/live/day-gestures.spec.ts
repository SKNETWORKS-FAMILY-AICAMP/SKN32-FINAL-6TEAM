import { expect, test, type Page } from "@playwright/test";
import { mockServer } from "./helpers";
import { openFinished, type Json } from "./plan-check-kit";

/**
 * `[2026-10-05 사용자 요청 — 날짜 전환 애니메이션 · 메뉴 목록 크기 조절]` 계획 확인 화면의 하루씩 보기. mock 서버 시험이다 — 화면 반응만 본다(실기기 손가락 감각은 못 봤다).
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
// `[2026-10-13 CI 점검]` 새로 고친 직후에는 목록이 아직 없을 수 있다 — 그때는 null 을 돌려 expect.poll 이 다시 묻게 한다(예외로 끝나면 다시 묻지 않는다).
const zoomOf = (page: Page) => page.evaluate(() => { const list = document.querySelector("div[class*=dayZoom]"); return list ? Number(getComputedStyle(list).zoom) : null; });
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

test("두 손가락은 목록 크기와 날짜를 바꾸지 않고 진행 중인 날짜 넘기기를 취소한다", async ({ page, request }) => {
  await openFinished(page, request, withDays);
  await finger(page, "pointerdown", 150, 420, 1);
  await finger(page, "pointermove", 120, 420, 1);
  expect(await trackShift(page)).toBeCloseTo(-30, 0);
  await finger(page, "pointerdown", 250, 420, 2, false);
  await finger(page, "pointermove", 80, 420, 1);
  await finger(page, "pointermove", 300, 420, 2);
  await finger(page, "pointerup", 80, 420, 1);
  await finger(page, "pointerup", 300, 420, 2);
  expect(await zoomOf(page)).toBe(1);
  expect(await trackShift(page)).toBe(0);
  await expect(page.getByRole("tab", { name: /^1일차/ })).toHaveAttribute("aria-selected", "true");
  expect(await page.locator("div[class*=sheetBody]").evaluate((el) => getComputedStyle(el).touchAction)).toContain("pinch-zoom");
});

test("설정 화면에서 목록 크기를 바꾸면 돌아온 목록에 적용되고, 새로 열어도 기억하며 기본 크기로 복원한다", async ({ page, request }) => {
  // `[2026-10-13 메뉴 = 마이페이지]` 일정 목록 크기는 메뉴가 아니라 설정 화면(메뉴 › 설정)에 있다 — 거기서 바꾸고 뒤로 오면 목록이 그 크기다.
  await openFinished(page, request, withDays);
  const toSettings = async () => {
    await page.getByRole("button", { name: "메뉴", exact: true }).click();
    await page.getByRole("dialog", { name: "메뉴" }).getByRole("link", { name: /^설정/ }).click();
    await expect(page).toHaveURL(/\/mypage$/);
  };
  const controls = page.getByRole("group", { name: "일정 목록 크기", exact: true });
  const increase = controls.getByRole("button", { name: "일정 목록 확대", exact: true });
  const reduce = controls.getByRole("button", { name: "일정 목록 축소", exact: true });
  await toSettings();
  for (let i = 0; i < 3; i++) await increase.click();
  await expect(controls.locator("output")).toHaveText("130%");
  await expect(increase).toBeDisabled();
  await page.goBack();
  await expect.poll(() => zoomOf(page)).toBe(1.3);
  if (process.env.LIST_ZOOM_SHOTS) await page.screenshot({ path: `${process.env.LIST_ZOOM_SHOTS}/menu-list-zoom-130.png` });
  await page.reload();
  await expect.poll(() => zoomOf(page)).toBe(1.3);
  await toSettings();
  for (let i = 0; i < 5; i++) await reduce.click();
  await expect(controls.locator("output")).toHaveText("80%");
  await expect(reduce).toBeDisabled();
  await page.goBack();
  await expect.poll(() => zoomOf(page)).toBe(0.8);
  await toSettings();
  await controls.getByRole("button", { name: "기본 크기", exact: true }).click();
  await expect(controls.locator("output")).toHaveText("100%");
  await page.goBack();
  await expect.poll(() => zoomOf(page)).toBe(1);
});
