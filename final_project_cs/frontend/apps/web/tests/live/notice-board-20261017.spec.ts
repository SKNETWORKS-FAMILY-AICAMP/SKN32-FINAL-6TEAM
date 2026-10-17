import { expect, test, type Page } from "@playwright/test";
import { mockServer, openNotices, start, TRIP_ID, tripScreen } from "./helpers";

/**
 * `[2026-10-17 사용자 결정 — ST4F-604]` 운영 앱 공지를 여행 화면 밖에서도 본다. mock 서버 시험이다(화면 반응만 본다 — 실서버 아님).
 *   - 공지사항(`/notices`, 메뉴 「공지사항」 · 목업 A안): 문의함 칸에 게시 중 → 종료, 제목 앞 「게시 중」 · 「종료」, 한 쪽 10줄 · 쪽 단추. 줄을 누르면 공지 한 장 화면.
 *   - 여행 화면 알림 센터의 「공지」 탭(`[2026-10-17 ST4F-606]` 옛: 맨 위 「서비스 공지」 칸): 배너와 같은 모양. 종에는 안 본 서비스 공지도 더하고, 공지 탭을 보면 읽음.
 */
test.beforeEach(async ({ request }) => {
  await mockServer(request).reset();
});

const rows = (page: Page) => page.locator("[data-notice-box] a[data-notice]");
const pager = (page: Page) => page.getByRole("navigation", { name: "공지 페이지 이동" });
const bell = (page: Page) => page.locator("#trip-bell");

test("공지사항: 게시 중이 위 · 종료가 아래, 제목 앞 딱지, 한 쪽 10줄을 쪽 단추로 넘기고 칸 높이는 그대로다", async ({ page, request }) => {
  await start(page);
  await mockServer(request).scenario({ noticeBoard: "many" });                      // 게시 중 3 · 종료 12
  await page.setViewportSize({ width: 402, height: 718 });                            // 아이폰 17 · 16 Pro 의 iOS 26 Safari 보이는 높이
  await page.goto("/notices");
  await expect(page.getByRole("heading", { name: "공지사항", level: 1 })).toBeVisible();
  await expect(rows(page)).toHaveCount(10);
  await expect(rows(page).nth(0)).toContainText("게시 중");
  await expect(rows(page).nth(0)).toContainText("채팅 답변이 늦어요");
  await expect(rows(page).nth(2)).toContainText("게시 중");
  await expect(rows(page).nth(3)).toContainText("종료");
  await expect(rows(page).nth(3)).toContainText("지난 공지 1");
  const first = await rows(page).nth(0).innerText();
  expect(first.indexOf("게시 중")).toBeLessThan(first.indexOf("채팅 답변이 늦어요"));        // 딱지가 제목 앞
  await expect(rows(page).nth(0)).toContainText("10.17");                                    // 게시 시작일
  const box = page.locator("[data-notice-box]");
  const height = (await box.boundingBox())!.height;
  expect(Math.round(height)).toBe(459);
  const pagerBottom = (await pager(page).boundingBox())!;
  expect(pagerBottom.y + pagerBottom.height).toBeLessThanOrEqual(718);                     // 10줄이어도 쪽 단추까지 한 화면
  await expect(pager(page).getByRole("button", { name: "이전 페이지" })).toBeDisabled();
  await pager(page).getByRole("button", { name: "2페이지" }).click();
  await expect(rows(page)).toHaveCount(5);
  await expect(rows(page).nth(0)).toContainText("지난 공지 8");
  await expect(rows(page).nth(0)).toContainText("종료");
  await expect(pager(page).getByRole("button", { name: "2페이지" })).toHaveAttribute("aria-current", "page");
  await expect(pager(page).getByRole("button", { name: "다음 페이지" })).toBeDisabled();
  expect(Math.round((await box.boundingBox())!.height)).toBe(459);                          // 줄이 적은 쪽에서도 칸이 줄지 않는다
});

test("공지 줄을 누르면 공지 한 장 화면 — 게시 중 · 종류 · 게시 기간 · 본문, 「공지사항」으로 돌아간다", async ({ page, request }) => {
  await start(page);
  await mockServer(request).scenario({ noticeBoard: "many" });
  await page.goto("/notices");
  await rows(page).nth(0).click();
  await expect(page).toHaveURL(/\/notices\/b-down$/);
  await expect(page.getByRole("heading", { name: "공지", level: 1 })).toBeVisible();
  const card = page.getByRole("article", { name: "채팅 답변이 늦어요" });
  await expect(card).toContainText("게시 중");
  await expect(card).toContainText("기능 차질·장애");
  await expect(card).toContainText("게시 10.17 14:00 ~ 10.17 20:00");
  await expect(card).toContainText("모델 서버가 느려");
  await expect(card).toHaveAttribute("data-tone", "error");
  await page.getByRole("main").getByRole("link", { name: "공지사항" }).click();
  await expect(page).toHaveURL(/\/notices$/);
  await page.goto("/notices/no-such-notice");
  await expect(page.getByRole("main").getByRole("alert")).toContainText("이 공지를 찾을 수 없어요");
});

test("게시판이 없는 옛 서버(404)는 준비 중, 공지가 하나도 없으면 빈 칸 문장 — 둘을 섞지 않는다", async ({ page, request }) => {
  await start(page);
  await page.goto("/notices");
  await expect(page.locator("[data-notice-box]")).toContainText("공지 목록은 아직 준비 중이에요.");
  await expect(rows(page)).toHaveCount(0);
  await mockServer(request).scenario({ noticeBoard: "none" });
  await page.reload();
  await expect(page.locator("[data-notice-box]")).toContainText("아직 올라온 공지가 없어요.");
  await expect(page.locator("[data-notice-box]")).not.toContainText("준비 중");
});

test("약관 동의 전에도 공지사항과 공지 한 장은 열린다", async ({ page, request }) => {
  await start(page, null);                                                             // 처음 온 브라우저 — 동의 기록 없음
  await mockServer(request).scenario({ noticeBoard: "many" });
  await page.goto("/notices");
  await expect(page.getByRole("heading", { name: "공지사항", level: 1 })).toBeVisible();
  await expect(rows(page)).toHaveCount(10);
  await page.goto("/notices/b-plan");
  await expect(page.getByRole("article", { name: "오늘 밤 23시 서버 점검" })).toBeVisible();
  await expect(page).toHaveURL(/\/notices\/b-plan$/);                                    // 약관 화면으로 보내지 않는다
});

test("메뉴 「공지사항」 줄은 게시 중인 공지 수를 말하고 게시판으로 간다", async ({ page, request }) => {
  await start(page);
  await page.goto("/trips");
  await page.getByRole("button", { name: "메뉴" }).click();
  await expect(page.getByRole("link", { name: /공지사항/ })).toContainText("게시 중인 공지 없음");
  await page.keyboard.press("Escape");
  await mockServer(request).scenario({ serviceNotice: "kinds" });
  await page.reload();
  await page.getByRole("button", { name: "공지 닫기" }).click();                       // 맨 위 배너가 머리를 덮는다 — 닫고 메뉴를 연다
  await page.getByRole("button", { name: "메뉴" }).click();
  const row = page.getByRole("link", { name: /공지사항/ });
  await expect(row).toContainText("게시 중 3개");
  await row.click();
  await expect(page).toHaveURL(/\/notices$/);
});

test("여행 화면 알림 센터 「공지」 탭 — 종에 안 본 공지가 더해지고, 공지 탭을 보면 읽음이 되어 새로고침 뒤에도 남지 않는다 (ST4F-606)", async ({ page, request }) => {
  await start(page);
  await mockServer(request).scenario({ serviceNotice: "kinds" });                    // 안내 · 장애 · 점검 예고
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(tripScreen(page)).toBeVisible();
  await page.getByRole("button", { name: "공지 닫기" }).click();
  await expect(bell(page)).toHaveAccessibleName("알림 센터 열기 · 읽지 않은 알림 5개");   // 여행 알림 2 + 서비스 공지 3
  const center = await openNotices(page);
  await expect(center.locator("[data-service-notices]")).toHaveCount(0);             // 맨 위 칸이 아니라 탭 안
  await expect(center.getByRole("tab", { name: /받은 알림/ })).toHaveAttribute("aria-selected", "true");   // 새 여행 알림이 먼저
  const serviceTab = center.getByRole("tab", { name: /^공지 3/ });
  await expect(serviceTab.getByRole("img", { name: "읽지 않은 알림" })).toHaveCount(1);
  await expect(bell(page)).toHaveAccessibleName("알림 센터 열기 · 읽지 않은 알림 3개");   // 여행 알림만 읽음 — 공지는 탭을 봐야
  await serviceTab.click();
  const items = center.locator("[data-service-notices] [data-tone]");
  await expect(items).toHaveCount(3);
  await expect(items.nth(0)).toHaveAttribute("data-tone", "error");                 // 배너처럼 장애가 가장 위
  await expect(items.nth(0)).toContainText("채팅 답변이 늦어요");
  await expect(center.getByRole("link", { name: /지난 공지까지 보기/ })).toHaveAttribute("href", "/notices");
  await expect(bell(page)).toHaveAccessibleName("알림 센터 열기");
  await expect(serviceTab.getByRole("img", { name: "읽지 않은 알림" })).toHaveCount(0);
  await page.reload();
  await expect(tripScreen(page)).toBeVisible();
  await expect(bell(page)).toHaveAccessibleName("알림 센터 열기");                    // 이 브라우저가 기억한다
});

test("새 여행 알림은 없고 새 공지만 있으면 알림 센터가 「공지」 탭으로 열린다 (ST4F-606)", async ({ page, request }) => {
  await start(page);
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(tripScreen(page)).toBeVisible();
  let center = await openNotices(page);                                              // 받은 알림 탭이 보여 주면 여행 알림은 읽음
  await center.getByRole("button", { name: "알림 센터 닫기" }).click();
  await mockServer(request).scenario({ serviceNotice: "one" });
  await page.reload();
  await expect(tripScreen(page)).toBeVisible();
  await page.getByRole("button", { name: "공지 닫기" }).click();
  await expect(bell(page)).toHaveAccessibleName("알림 센터 열기 · 읽지 않은 알림 1개");
  center = await openNotices(page);
  await expect(center.getByRole("tab", { name: /^공지/ })).toHaveAttribute("aria-selected", "true");
  await expect(center.getByRole("tabpanel")).toContainText("서비스 점검 예정 안내");
  await expect(bell(page)).toHaveAccessibleName("알림 센터 열기");
});

test("서비스 공지가 없으면 「공지 0」 탭은 빈 문장과 공지사항 가는 길만 있고 종 수도 그대로다", async ({ page }) => {
  await start(page);
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(tripScreen(page)).toBeVisible();
  await expect(bell(page)).toHaveAccessibleName("알림 센터 열기 · 읽지 않은 알림 2개");
  const center = await openNotices(page);
  const serviceTab = center.getByRole("tab", { name: /^공지 0/ });
  await expect(serviceTab.getByRole("img")).toHaveCount(0);
  await serviceTab.click();
  await expect(center.getByRole("tabpanel")).toContainText("지금 게시 중인 공지가 없어요.");
  await expect(center.getByRole("link", { name: /지난 공지까지 보기/ })).toBeVisible();
});
