import { expect, test, type CDPSession, type Page } from "@playwright/test";
import { mockServer } from "./helpers";
import { openFinished, type Json } from "./plan-check-kit";

/**
 * `[2026-10-06]` 진짜 터치 입력으로 본 손가락 동작(mock 서버 시험 — 서버 응답이 아니라 화면 반응을 본다). 앞의 `day-gestures.spec.ts` · `time-direct-drag.spec.ts` 는 포인터 이벤트를 코드로 흉내 낸 것이라
 * 브라우저의 터치 처리(`touch-action` 으로 스크롤을 넘기거나 뺏는 것, 취소 이벤트)를 거치지 않는다. 여기서는 브라우저의 터치 입력 통로(CDP `Input.dispatchTouchEvent`)로 손가락을 보내, 모바일 화면 설정(`isMobile`)에서
 * 그 처리까지 지나간다. ★그래도 실제 손가락·실제 기기가 아니다 — 손가락의 크기·떨림·관성 스크롤·운영체제의 뒤로가기 제스처는 못 본다.
 */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });
test.use({ hasTouch: true, isMobile: true, viewport: { width: 390, height: 844 } });

const DAY_TWO_STOP: Json = {
  id: "0-3", source_id: "s1", index: 3, title: "N서울타워", kind: "activity", day: 2, date: "2026-10-02", starts_at: "10:00", ends_at: "11:30",
  locked: false, status: "keep", can_lock: true, place_state: "found", candidates_hint: null,
  place: { name: "N서울타워", latitude: 37.5512, longitude: 126.9882, source: "tour_api", kind: null, content_id: null, content_type_id: null },
  rows: [{ row: "place", result: "ok", text: "관광공사 정보로 찾았어요" }],
};
const withDays = (view: Json) => { view.review.items.push(DAY_TWO_STOP); };

type Finger = { x: number; y: number; id: number };
/** 브라우저의 터치 통로로 손가락들을 보낸다 — 한 번 보낼 때마다 잠깐 기다려 사람 손의 속도에 가깝게 한다. */
async function touch(cdp: CDPSession, type: "touchStart" | "touchMove" | "touchEnd", fingers: Finger[], wait = 40) {
  await cdp.send("Input.dispatchTouchEvent", { type, touchPoints: fingers.map((finger) => ({ x: finger.x, y: finger.y, id: finger.id })) });
  if (wait) await new Promise((resolve) => setTimeout(resolve, wait));
}
/** 한 손가락이 from 에서 to 까지 steps 번에 나눠 간다. */
async function drag(cdp: CDPSession, from: [number, number], to: [number, number], steps = 12, wait = 18) {
  await touch(cdp, "touchStart", [{ x: from[0], y: from[1], id: 1 }]);
  for (let step = 1; step <= steps; step += 1) await touch(cdp, "touchMove", [{ x: from[0] + ((to[0] - from[0]) * step) / steps, y: from[1] + ((to[1] - from[1]) * step) / steps, id: 1 }], wait);
  await touch(cdp, "touchEnd", [], 60);
}
const sheetBody = (page: Page) => page.locator("div[class*=sheetBody]");
const tab = (page: Page, name: RegExp | string) => page.getByRole("tab", { name });

test("진짜 터치: 왼쪽으로 쓸면 다음 날, 오른쪽으로 쓸면 이전 날이 된다", async ({ page, request }) => {
  await openFinished(page, request, withDays);
  const cdp = await page.context().newCDPSession(page);
  const box = (await sheetBody(page).boundingBox())!;
  const y = box.y + 110;                                                                            // 떠 있는 날짜 줄(위 64px) 아래의 목록에서 쓴다
  await expect(tab(page, /^1일차/)).toHaveAttribute("aria-selected", "true");
  await drag(cdp, [box.x + box.width - 30, y], [box.x + 40, y + 6]);
  await expect(tab(page, /^2일차/)).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("article", { name: "N서울타워", exact: true })).toBeVisible();
  await drag(cdp, [box.x + 40, y], [box.x + box.width - 30, y + 6]);                                    // 왼쪽 끝(시간 · 원 자리)에서 시작해도 옆으로 쓸면 이전 날이다
  await expect(tab(page, /^1일차/)).toHaveAttribute("aria-selected", "true");
});

test("진짜 터치: 위아래로 끌면 목록이 스크롤될 뿐 날은 안 바뀐다", async ({ page, request }) => {
  await openFinished(page, request, withDays);
  const cdp = await page.context().newCDPSession(page);
  const box = (await sheetBody(page).boundingBox())!;
  const before = await sheetBody(page).evaluate((element) => element.scrollTop);
  await drag(cdp, [box.x + box.width / 2, box.y + box.height - 40], [box.x + box.width / 2 + 8, box.y + 30], 14);
  await expect(tab(page, /^1일차/)).toHaveAttribute("aria-selected", "true");                        // 날은 그대로
  await expect.poll(() => sheetBody(page).evaluate((element) => element.scrollTop), { timeout: 3000 }).toBeGreaterThan(before);   // 목록이 스크롤됐다(브라우저가 세로 이동을 가져갔다)
});

test("진짜 터치: 두 손가락을 오므리면 끝까지 오므린 뒤 전체 일정으로, 벌리면 하루 보기로 돌아온다", async ({ page, request }) => {
  await openFinished(page, request, withDays);
  const cdp = await page.context().newCDPSession(page);
  const box = (await sheetBody(page).boundingBox())!;
  const cx = box.x + box.width / 2, cy = box.y + 120;
  await touch(cdp, "touchStart", [{ x: cx - 60, y: cy, id: 1 }, { x: cx + 60, y: cy, id: 2 }]);       // 오므린다: 120px → 20px
  for (let step = 1; step <= 10; step += 1) {
    const half = 60 - (40 * step) / 10;
    await touch(cdp, "touchMove", [{ x: cx - half, y: cy, id: 1 }, { x: cx + half, y: cy, id: 2 }], 25);
  }
  await touch(cdp, "touchEnd", [], 80);
  await expect(page.getByRole("tab", { name: "전체" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("article", { name: "N서울타워", exact: true })).toBeVisible();            // 두 날이 이어진 개요
  await touch(cdp, "touchStart", [{ x: cx - 10, y: cy, id: 1 }, { x: cx + 10, y: cy, id: 2 }]);       // 벌린다: 20px → 280px
  for (let step = 1; step <= 10; step += 1) {
    const half = 10 + (130 * step) / 10;
    await touch(cdp, "touchMove", [{ x: cx - half, y: cy, id: 1 }, { x: cx + half, y: cy, id: 2 }], 25);
  }
  await touch(cdp, "touchEnd", [], 80);
  await expect(tab(page, /^1일차/)).toHaveAttribute("aria-selected", "true");
});

test("진짜 터치: 오므려 전체 일정이 된 뒤에도 옆으로 쓸면 보고 있던 날의 하루 보기로 돌아가고, 그다음 쓸기로 날이 바뀐다", async ({ page, request }) => {
  // `[2026-10-07 사용자 지적 — 확대 · 축소를 하다 보면 좌우로 넘기기가 막힌다]` 줄인 상태에서 조금 더 오므리면 전체 일정 보기가 되는데, 거기서는 옆으로 쓸어도 아무 일도 없었다.
  await openFinished(page, request, withDays);
  const cdp = await page.context().newCDPSession(page);
  const box = (await sheetBody(page).boundingBox())!;
  const cx = box.x + box.width / 2, cy = box.y + 120;
  await touch(cdp, "touchStart", [{ x: cx - 60, y: cy, id: 1 }, { x: cx + 60, y: cy, id: 2 }]);
  for (let step = 1; step <= 10; step += 1) { const half = 60 - (40 * step) / 10; await touch(cdp, "touchMove", [{ x: cx - half, y: cy, id: 1 }, { x: cx + half, y: cy, id: 2 }], 25); }
  await touch(cdp, "touchEnd", [], 80);
  await expect(page.getByRole("tab", { name: "전체" })).toHaveAttribute("aria-selected", "true");
  const y = box.y + 110;                                                                            // 떠 있는 날짜 줄(위 64px) 아래의 목록에서 쓴다
  await drag(cdp, [box.x + box.width - 30, y], [box.x + 40, y + 6]);
  await expect(tab(page, /^1일차/)).toHaveAttribute("aria-selected", "true");                        // 맨 위에 보이던 날(1일차)의 하루 보기
  await drag(cdp, [box.x + box.width - 30, y], [box.x + 40, y + 6]);
  await expect(tab(page, /^2일차/)).toHaveAttribute("aria-selected", "true");                        // 다시 평소처럼 넘어간다
});

test("진짜 터치: 수정 · 삭제는 평소엔 숨어 있고, 목록을 스크롤하면 가운데에 가까운 일정 하나에만 4초 동안 보인다", async ({ page, request }) => {
  // `[2026-10-07 사용자 지시]` 여행 중 손으로 쓰는 화면 — 잘못 누를 일을 줄이면서 필요할 때는 바로 누를 수 있게
  await openFinished(page, request, withDays);
  const cdp = await page.context().newCDPSession(page);
  const visibleEdits = () => page.locator('[id^="plan-edit-"]').evaluateAll((buttons) => buttons.filter((button) => getComputedStyle(button).visibility === "visible").length);
  await expect.poll(visibleEdits).toBe(0);                                                            // 닫힌 카드만 있을 때는 숨어 있다
  await sheetBody(page).evaluate((element) => { element.scrollTop = 0; element.scrollBy({ top: 40 }); });
  await expect.poll(visibleEdits).toBe(1);                                                            // 가운데에 가까운 하나만
  expect(await page.locator('li[data-type="item"][data-tools]').count()).toBe(1);
  await page.waitForTimeout(4_400);
  await expect.poll(visibleEdits).toBe(0);                                                            // 4초가 지나면 사라진다
  void cdp;
});

test("진짜 터치: 일정 시간을 잡고 끌면 시간이 바뀌고 목록은 스크롤되지 않는다", async ({ page, request }) => {
  await openFinished(page, request);
  const cdp = await page.context().newCDPSession(page);
  const handle = page.getByRole("button", { name: /^경복궁 관람 시간 고치기/ });
  const box = (await handle.boundingBox())!;
  const x = box.x + box.width / 2, y = box.y + box.height / 2;
  const scrollBefore = await sheetBody(page).evaluate((element) => element.scrollTop);
  await touch(cdp, "touchStart", [{ x, y, id: 1 }]);
  for (let step = 1; step <= 10; step += 1) await touch(cdp, "touchMove", [{ x, y: y + step * 3, id: 1 }], 25);      // 30px = 15분
  await expect(page.locator('[data-overlay="time"]')).toBeVisible();                                 // 끄는 동안 하루 미니맵
  await touch(cdp, "touchEnd", [], 80);
  await expect(page.getByRole("status").filter({ hasText: "1개 일정의 시간을 바꿨어요" })).toBeVisible();
  expect(await sheetBody(page).evaluate((element) => element.scrollTop)).toBe(scrollBefore);          // 목록은 안 움직였다
});
