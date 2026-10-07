import { expect, test } from "@playwright/test";
import { mockServer, openNotices, start, TRIP_ID, tripScreen } from "./helpers";

/**
 * `[2026-10-07 사용자 결정 — 목업 C안 ① 알림 센터]` 종 · 알림 센터 · 새 알림 막대. mock 서버 시험이다 — 화면 반응만 본다.
 *   - 종에는 이 브라우저가 아직 안 본 알림 수가 붙는다. 「받은 알림」 탭이 보여 주면 읽음이고, 이 브라우저가 기억한다(★서버에 읽음 상태가 없다 — 다른 기기에서는 다시 새 알림이다).
 *   - 여행 화면이 열려 있는 동안 서버가 알림을 보내면 알림 막대가 뜨고 「알림 보기」로 받은 알림 탭이 열린다. 화면을 열 때 이미 있던 알림은 막대로 띄우지 않는다.
 *   - 할 일의 「선택이 필요해요」에서 「일정에서 보기」를 누르면 센터가 닫히고 그 일정이 목록에서 펼쳐진다.
 */
test.beforeEach(async ({ page, request }) => {
  await mockServer(request).reset();
  await start(page);
});

const bell = (page: import("@playwright/test").Page) => page.locator("#trip-bell");

test("종은 안 본 알림 수를 말하고, 받은 알림 탭을 보면 읽음이 되어 새로고침 뒤에도 수가 없다 — 이번에 처음 본 알림에는 점이 남는다", async ({ page }) => {
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(tripScreen(page)).toBeVisible();
  await expect(bell(page)).toHaveAccessibleName("알림 센터 열기 · 읽지 않은 알림 2개");
  await expect(bell(page)).toContainText("2");
  const center = await openNotices(page);
  await expect(center.getByRole("tab", { name: /받은 알림/ })).toHaveAttribute("aria-selected", "true");
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
  await expect(again.getByRole("tab", { name: /살펴볼 점/ })).toHaveAttribute("aria-selected", "true");     // 새 알림이 없으면 마지막 탭(처음은 살펴볼 점)
});

test("탭은 화살표 키로 옮겨 가고, 탭마다 서버가 준 수를 단다", async ({ page }) => {
  await page.goto(`/trips/${TRIP_ID}`);
  const center = await openNotices(page);
  await center.getByRole("tab", { name: /받은 알림/ }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(center.getByRole("tab", { name: /변경 이력/ })).toBeFocused();
  await expect(center.getByRole("tab", { name: /변경 이력/ })).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("ArrowRight");
  await expect(center.getByRole("tab", { name: /살펴볼 점/ })).toHaveAttribute("aria-selected", "true");
  await expect(center.getByRole("tabpanel")).toContainText("하루가 빡빡해요");
});

test("화면이 열려 있는 동안 서버가 선택 요청을 보내면 그 일정의 번호 · 이름 · 「선택 요청」 막대가 뜨고, 「알림 보기」로 받은 알림 탭이 열린다", async ({ page, request }) => {
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
  await expect(bell(page)).toHaveAccessibleName("알림 센터 열기 · 읽지 않은 알림 3개");
  await bar.getByRole("button", { name: "알림 보기" }).click();
  const center = page.getByRole("dialog", { name: "알림" });
  await expect(center.getByRole("tab", { name: /받은 알림/ })).toHaveAttribute("aria-selected", "true");
  await expect(center.getByRole("region", { name: /선택이 필요해요/ })).toBeVisible();                     // 할 일 맨 위
  await expect(center.getByRole("heading", { name: /할 일 1/ })).toBeVisible();
});

test("선택 요청의 「일정에서 보기」는 센터를 닫고 그 일정을 목록에서 펼친다", async ({ page, request }) => {
  await mockServer(request).scenario({ proposals: "open" });
  await page.goto(`/trips/${TRIP_ID}`);
  const center = await openNotices(page);
  await center.getByRole("region", { name: /선택이 필요해요/ }).getByRole("button", { name: "일정에서 보기" }).click();
  await expect(page.getByRole("dialog", { name: "알림" })).toHaveCount(0);
  await expect(page.locator("#stop-button-i-c")).toHaveAttribute("aria-expanded", "true");
  await expect(tripScreen(page).locator('li[data-selected="true"]')).toContainText("점심 식당");
});
