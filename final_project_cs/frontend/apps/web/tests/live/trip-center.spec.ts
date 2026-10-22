import { expect, test } from "@playwright/test";
import { beforeTheTrip, mockServer, openNotices, start, TRIP_ID, tripScreen } from "./helpers";

/**
 * `[2026-10-07 사용자 결정 — 목업 C안 ① 알림 센터]` 종 · 알림 센터 · 새 알림 막대. mock 서버 시험이다 — 화면 반응만 본다.
 *   - 종에는 이 브라우저가 아직 안 본 알림 수가 붙는다. 「소식」 탭이 보여 주면 읽음이고, 이 브라우저가 기억한다(★서버에 읽음 상태가 없다 — 다른 기기에서는 다시 새 알림이다).
 *   - 여행 화면이 열려 있는 동안 서버가 알림을 보내면 알림 막대가 뜬다. 화면을 열 때 이미 있던 알림은 막대로 띄우지 않는다.
 *   - `[2026-10-22 ST4F-723 구성 Ⓑ]` 탭은 셋(할 일 · 소식 · 공지)이고 「답이 필요해요」 머리는 없다. 「할 일」의 선택 요청 카드(`data-center-proposal`)의 일정 줄 「상세 보기」를 누르면
 *     센터가 닫히고 그 일정의 상세 보기가 열린다(옛 「일정에서 보기」 — 목록 카드를 펼치던 것). 선택 요청 막대(Ⓣ1)의 단추도 「상세 보기」다.
 */
test.beforeEach(async ({ page, request }) => {
  await mockServer(request).reset();
  await start(page);
});

const bell = (page: import("@playwright/test").Page) => page.locator("#trip-bell");

test("종은 안 본 알림 수를 말하고, 소식 탭을 보면 읽음이 되어 새로고침 뒤에도 수가 없다 — 이번에 처음 본 알림에는 점이 남는다", async ({ page }) => {
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(tripScreen(page)).toBeVisible();
  await expect(bell(page)).toHaveAccessibleName("알림 센터 열기 · 읽지 않은 알림 2개");
  await expect(bell(page)).toContainText("2");
  const center = await openNotices(page);
  await expect(center.getByRole("tab", { name: /^소식/ })).toHaveAttribute("aria-selected", "true");   // 기다리는 답이 없고 안 본 소식이 있으면 소식부터
  await expect(center.getByRole("tabpanel").getByRole("img", { name: "새 알림" })).toHaveCount(2);          // 이번에 처음 본 것
  await expect(bell(page)).toHaveAccessibleName("알림 센터 열기");                                           // 본 순간 읽음
  await center.getByRole("button", { name: "알림 센터 닫기" }).click();
  await expect(bell(page)).toBeFocused();
  await bell(page).click();
  await expect(page.getByRole("dialog", { name: "알림" }).getByRole("tabpanel").getByRole("img", { name: "새 알림" })).toHaveCount(0);   // 다시 열면 점이 없다
  await page.reload();
  await expect(tripScreen(page)).toBeVisible();
  await expect(bell(page)).toHaveAccessibleName("알림 센터 열기");                                           // 이 브라우저가 기억한다
  const again = await openNotices(page);
  await expect(again.getByRole("tab", { name: /^할 일/ })).toHaveAttribute("aria-selected", "true");     // 새 알림이 없으면 마지막 탭(처음은 할 일)
});

test("탭은 화살표 키로 옮겨 가고, 탭마다 서버가 준 수를 단다", async ({ page }) => {
  await page.goto(`/trips/${TRIP_ID}`);
  const center = await openNotices(page);
  await center.getByRole("tab", { name: /^소식/ }).click();                                                // 화살표는 고른 탭에서 옮겨 간다(알림을 읽기 전에 열면 할 일이 골라져 있다)
  await page.keyboard.press("ArrowRight");
  await expect(center.getByRole("tab", { name: /^공지/ })).toBeFocused();                                // `[2026-10-22 ST4F-723 구성 Ⓑ]` 탭 셋 — 소식 다음은 공지
  await expect(center.getByRole("tab", { name: /^공지/ })).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("ArrowRight");
  await expect(center.getByRole("tab", { name: /^할 일/ })).toHaveAttribute("aria-selected", "true");     // 끝에서 처음(할 일)으로
  await expect(center.getByRole("tabpanel")).toContainText("하루가 빡빡해요");                            // 할 일 아래 「살펴볼 점」
});

test("화면이 열려 있는 동안 서버가 선택 요청을 보내면 그 일정의 번호 · 이름 · 「선택 요청」 막대가 뜨고, 「상세 보기」로 그 일정의 상세 보기가 열린다", async ({ page, request }) => {
  await beforeTheTrip(page);                                                                                  // `[2026-10-21]` 모방 제안은 10-01 23:00 에 끝난다 — 지난 제안은 고를 수 없어 걸러진다
  // `[2026-10-22 ST4F-723 Ⓣ1]` 막대의 단추는 그 제안을 지금 고를 수 있을 때(열림 · 여행 판이 제안의 판과 같음)만 「상세 보기」다. 알림 · 여행 다시 읽기의 도착 순서에 따라
  //   막대를 만들 때의 판이 달라지지 않게, 여행은 처음부터 제안 p-1 의 판(2)으로 둔다.
  await page.route(`**/v1/web/trips/${TRIP_ID}`, async (route) => {
    if (route.request().method() !== "GET") { await route.continue(); return; }
    const response = await route.fetch();
    await route.fulfill({ response, json: { ...(await response.json()), version: 2 } });
  });
  const server = mockServer(request);
  await server.scenario({ bell: "on" });
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(tripScreen(page)).toBeVisible();
  await expect(bell(page)).toHaveAccessibleName("알림 센터 열기 · 읽지 않은 알림 2개");
  await expect(page.getByRole("status").filter({ hasText: "선택 요청" })).toHaveCount(0);                 // 열 때 있던 알림은 막대로 띄우지 않는다
  await server.scenario({ proposals: "open" });
  await expect.poll(() => server.ring(["notice", "proposal"])).toBeGreaterThan(0);
  const bar = page.getByRole("status").filter({ hasText: "선택 요청" });
  await expect(bar).toContainText("점심 식당");                                                               // 서버가 고른 그 일정
  await expect(bar).toContainText("3");                                                                       // 그날 지도 번호
  await expect(bar).toContainText("점심 식당이 문을 닫았어요. 대체 식당을 골라 주세요.");                       // 서버의 문장 그대로
  await expect(bar).toContainText("2026-10-01 23:00 까지");                                                  // 서버가 기다리는 기한
  await expect(bell(page)).toHaveAccessibleName("알림 센터 열기 · 읽지 않은 알림 3개");
  await bar.getByRole("button", { name: "상세 보기" }).click();                                              // `[2026-10-22 ST4F-723 Ⓣ1]` 옛 「알림 보기」 → 받은 알림 탭
  await expect(page.getByRole("dialog", { name: "알림" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "점심 식당 상세", level: 3 })).toBeVisible();
  await expect(page.locator('[data-card-id="i-c"] [data-proposal-ask="p-1"]')).toContainText("대체 식당 A");   // 그 선택은 상세 보기에서 답한다(ST4F-704)
  // 종으로 열면 기다리는 선택이 있어 「할 일」부터 — 선택 요청 카드가 서고, 탭 수는 강조된 1
  await page.getByRole("button", { name: "상세 보기 닫기" }).click();
  const center = await openNotices(page);
  await expect(center.getByRole("tab", { name: /^할 일/ })).toHaveAttribute("aria-selected", "true");
  await expect(center.getByRole("tab", { name: /^할 일/ }).locator("[data-hot]")).toHaveText("1");
  await expect(center.locator('[data-center-proposal="p-1"]')).toBeVisible();
  await expect(bell(page)).toHaveAccessibleName("알림 센터 열기 · 읽지 않은 알림 2개");                       // 할 일이 보여 준 선택 요청만 읽음 — 앞의 두 알림은 소식 탭을 봐야
});

test("선택 요청 카드의 「상세 보기」는 센터를 닫고 그 일정의 상세 보기를 열며, ← 로 돌아오면 그 일정이 목록에서 펼쳐진다", async ({ page, request }) => {
  // `[2026-10-22 ST4F-715]` 화면은 만료된 제안을 거른다 — 모방 서버 제안(2026-10-01 23:00 만료) 앞의 시각으로 시계를 둔다
  await beforeTheTrip(page);
  await mockServer(request).scenario({ proposals: "open" });
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(page.locator('[data-stop-ask="i-c"]')).toBeAttached();                                      // 제안을 읽은 뒤에 연다 — 첫 탭은 열 때 한 번 정한다
  const center = await openNotices(page);
  await expect(center.getByRole("tab", { name: /^할 일/ })).toHaveAttribute("aria-selected", "true");     // 기다리는 선택이 있으면 할 일부터
  // `[2026-10-22 ST4F-723 구성 Ⓑ]` 옛 「일정에서 보기」(목록 카드를 펼침) → 일정 줄의 「상세 보기」(목록 카드의 「상세 보기」와 같다)
  await center.locator('[data-center-proposal="p-1"]').getByRole("button", { name: "상세 보기", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "알림" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "점심 식당 상세", level: 3 })).toBeFocused();
  await expect(page.locator('[data-card-id="i-c"]')).toHaveAttribute("data-active", "true");
  await page.getByRole("button", { name: "상세 보기 닫기" }).click();
  await expect(page.locator("#stop-button-i-c")).toHaveAttribute("aria-expanded", "true");
  await expect(tripScreen(page).locator('li[data-selected="true"]')).toContainText("점심 식당");
});

test("알림 문장 속 https 주소는 채팅처럼 누를 수 있는 링크이고, https 가 아닌 주소는 글자 그대로다", async ({ page }) => {
  // 실서버의 등록 알림은 「계획서: <주소>」를 문장에 싣는다(2026-10-08 확인). 링크 규칙은 채팅의 답과 같다(`linked-text.tsx`, https 만).
  const at = (minute: number) => `2026-10-01T08:${String(minute).padStart(2, "0")}:00+09:00`;
  await page.route(`**/v1/web/trips/${TRIP_ID}/notices`, async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.notices = [...body.notices,
      { key: "n-link", type: "change_notice", kind: null, text: "여행 일정이 준비되었습니다 — 내 여행. 계획서: https://plan.example/plan/x?t=abc", version: 1, proposal_id: null, delivery: "sent", at: at(0) },
      { key: "n-http", type: "guidance", kind: null, text: "로컬 계획서: http://127.0.0.1:8042/plan/x?t=abc", version: 1, proposal_id: null, delivery: "sent", at: at(10) }];
    await route.fulfill({ response, json: body });
  });
  await page.goto(`/trips/${TRIP_ID}`);
  const center = await openNotices(page);
  await center.getByRole("tab", { name: /^소식/ }).click();                                                  // `[2026-10-22 ST4F-723]` 옛 「받은 알림」
  const list = center.getByRole("tabpanel");
  // `[2026-10-13 develop 병합]` 링크 글자는 사이트 이름만 보인다(role-manager ac3e5b0f — `linked-text.tsx` 「www. 뗀 호스트」). 가는 곳은 그대로 전체 주소다.
  const link = list.getByRole("link", { name: "plan.example", exact: true });
  await expect(link).toHaveAttribute("href", "https://plan.example/plan/x?t=abc");
  await expect(link).toHaveAttribute("target", "_blank");
  await expect(list.getByRole("link", { name: /127\.0\.0\.1/ })).toHaveCount(0);
  await expect(list).toContainText("로컬 계획서: http://127.0.0.1:8042/plan/x?t=abc");
});
