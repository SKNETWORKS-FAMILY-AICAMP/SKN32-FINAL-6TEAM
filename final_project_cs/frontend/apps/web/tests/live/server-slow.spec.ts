import { expect, test, type Page } from "@playwright/test";
import { checkPlan, mockServer, start } from "./helpers";

/**
 * `[2026-10-06 사용자 지적 — 서버가 1분 넘게 답이 없는데 아무 알림이 없다]` 서버가 늦으면 화면이 말한다: 답을 기다리는 호출이 8초 넘으면 맨 위에 안내(점점 강해지고, 답이 오면 사라지며, 닫을 수 있다),
 * 읽는 화면은 새 소식이 30초 · 60초 없으면 따로 말한다. 테스트용 mock 서버로 도는 자동 시험이다(화면 반응을 본다 — 실서버 확인 아님).
 */
const PLAN = "10/1 09:00 경복궁 관람";
// `[2026-10-16 사용자 결정 — CI 시간 줄이기 ③]` 화면의 기다림 계산(`Date.now` · `setInterval`)은 가짜 시계로 건너뛴다 —
//   「아직 안 넘어갔다 · 아직 안 떴다」는 시간을 건너뛴 뒤 화면이 다시 그려질 틈(0.3초)만 실제로 기다리고 본다.
//   모방 서버가 늦게 답하는 시간(intakeDelay)은 실제 시간이라, 화면을 확인할 동안만 버티게 짧게 둔다.
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const banner = (page: Page) => page.getByRole("status").filter({ hasText: "서버 응답이 늦어지고 있어요" });
// 늦게 답하는 접수 호출이 실제로 나간 때 — 화면은 이 호출이 나갈 때 기다림을 세기 시작한다(`beginWait`). 느린 CI 에서는 주소가 먼저 바뀌어,
// 주소만 보고 시계를 건너뛰면 세기 전에 건너뛴 것이 된다(2026-10-16 CI 실행 38861330869 에서 실패).
const intakeSent = (page: Page) => page.waitForRequest((r) => r.method() === "POST" && new URL(r.url()).pathname.endsWith("/v1/web/trip-intakes"));

async function send(page: Page) {
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await checkPlan(page);
}

test("서버가 답을 안 주고 10초가 넘으면 맨 위에 안내가 뜨고(몇 초째인지 함께), 답이 오면 저절로 사라진다. 빨리 답하는 평소에는 아무것도 안 뜬다", async ({ page, request }) => {
  test.setTimeout(60_000);
  const server = mockServer(request);
  await start(page);
  // 평소: 안내가 없다
  await server.scenario({ readingPolls: 0 });
  await send(page);
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible({ timeout: 15_000 });
  await expect(banner(page)).toHaveCount(0);
  // 서버가 늦다: 접수에 답하는 데 실제 8초 — 그동안 화면 시계를 5초 · 11초로 건너뛰어 본다(첫 안내가 10초)
  await page.clock.install();
  await server.scenario({ intakeDelay: 8_000, readingPolls: 0 });
  const sent = intakeSent(page);
  await send(page);
  await expect(page).toHaveURL(/\/intakes\/starting$/);
  await sent;
  await page.clock.fastForward(5_000);
  await page.waitForTimeout(300);
  await expect(banner(page)).toHaveCount(0);                                                           // 아직 5초 — 말할 때가 아니다
  await page.clock.fastForward(6_000);
  await expect(banner(page)).toBeVisible({ timeout: 5_000 });
  await expect(banner(page)).toContainText("잠시만 더 기다려 주세요.");
  await expect(banner(page)).toContainText("초째");
  const box = (await banner(page).boundingBox())!;
  expect(box.y).toBeLessThan(40);                                                                      // 화면 맨 위에 떠 있다
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(1280);
  await expect(banner(page)).toHaveCount(0, { timeout: 15_000 });                                      // 서버가 답하자 사라진다
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible({ timeout: 15_000 });
});

test("30초가 넘으면 더 강한 문장으로 바뀌고, 닫기를 누르면 그 호출에는 다시 뜨지 않는다", async ({ page, request }) => {
  test.setTimeout(90_000);
  const server = mockServer(request);
  await start(page);
  await page.clock.install();
  await server.scenario({ intakeDelay: 10_000, readingPolls: 0 });
  const sent = intakeSent(page);
  await send(page);
  await expect(page).toHaveURL(/\/intakes\/starting$/);
  await sent;                                                                                          // 늦은 호출이 나간 뒤에 건너뛴다
  await page.clock.fastForward(11_000);
  await expect(banner(page)).toBeVisible({ timeout: 5_000 });
  await page.clock.fastForward(20_000);
  await expect(page.getByRole("status").filter({ hasText: "서버가 아직 답하지 않았어요" })).toBeVisible({ timeout: 5_000 });
  await expect(page.getByRole("status").filter({ hasText: "계속 안 되면 잠시 뒤에 다시 시도해 주세요." })).toBeVisible();
  await page.getByRole("status").filter({ hasText: "서버가 아직 답하지 않았어요" }).getByRole("button", { name: "닫기" }).click();
  await expect(page.getByRole("status").filter({ hasText: "서버가 아직 답하지 않았어요" })).toHaveCount(0);
  await page.clock.fastForward(2_500);
  await page.waitForTimeout(300);
  await expect(page.getByRole("status").filter({ hasText: /서버(가 아직 답하지 않았어요| 응답이 늦어지고 있어요)/ })).toHaveCount(0);
});

test("계획을 읽는 동안 새 소식이 30초 없으면 읽는 화면이 「서버 소식이 한동안 없어요」라고 말하고, 읽기가 끝나면 사라진다", async ({ page, request }) => {
  test.setTimeout(90_000);
  const server = mockServer(request);
  await start(page);
  await server.scenario({ readingPolls: 999 });
  await page.clock.install();
  await send(page);
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);
  const note = page.getByRole("status").filter({ hasText: "서버 소식이 한동안 없어요" });
  await expect(page.getByRole("heading", { name: "계획을 확인하고 있어요", level: 1 })).toBeVisible();
  await page.clock.fastForward(1_000);                                                                 // 첫 틱 — 조용한 시간을 재기 시작한다(use-quiet.ts)
  await page.clock.fastForward(20_000);
  await page.waitForTimeout(300);
  await expect(note).toHaveCount(0);                                                                   // 20초는 아직이다
  await page.clock.fastForward(11_000);
  await expect(note).toBeVisible({ timeout: 5_000 });
  await expect(note).toContainText("조금 더 기다리거나, 뒤로 가서 다시 보낼 수 있어요.");
  await expect(note).toContainText("30초 이상 새 진행 소식이 없어요.");
  await note.getByRole("button", { name: "닫기", exact: true }).click();
  await expect(note).toHaveCount(0);
  await page.clock.fastForward(1_200); // 다음 quiet 갱신이 닫은 토스트를 다시 띄우지 않습니다.
  await page.waitForTimeout(300);
  await expect(note).toHaveCount(0);
  await server.scenario({ readingPolls: 0 });
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible({ timeout: 20_000 });
  await expect(note).toHaveCount(0);
});
