import { expect, test, type Page } from "@playwright/test";
import { checkPlan, mockServer, start } from "./helpers";

/**
 * `[2026-10-06 사용자 지적 — 서버가 1분 넘게 답이 없는데 아무 알림이 없다]` 서버가 늦으면 화면이 말한다: 답을 기다리는 호출이 8초 넘으면 맨 위에 안내(점점 강해지고, 답이 오면 사라지며, 닫을 수 있다),
 * 읽는 화면은 새 소식이 30초 · 60초 없으면 따로 말한다. 테스트용 mock 서버로 도는 자동 시험이다(화면 반응을 본다 — 실서버 확인 아님).
 */
const PLAN = "10/1 09:00 경복궁 관람";
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const banner = (page: Page) => page.getByRole("status").filter({ hasText: "서버 응답이 늦어지고 있어요" });

async function send(page: Page) {
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await checkPlan(page);
}

test("서버가 답을 안 주고 8초가 넘으면 맨 위에 안내가 뜨고(몇 초째인지 함께), 답이 오면 저절로 사라진다. 빨리 답하는 평소에는 아무것도 안 뜬다", async ({ page, request }) => {
  test.setTimeout(60_000);
  const server = mockServer(request);
  await start(page);
  // 평소: 안내가 없다
  await server.scenario({ readingPolls: 0 });
  await send(page);
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible({ timeout: 15_000 });
  await expect(banner(page)).toHaveCount(0);
  // 서버가 늦다: 접수에 답하는 데 12초
  await server.scenario({ intakeDelay: 12_000, readingPolls: 0 });
  await send(page);
  await expect(page).toHaveURL(/\/intakes\/starting$/);
  await page.waitForTimeout(5_000);
  await expect(banner(page)).toHaveCount(0);                                                           // 아직 5초 — 말할 때가 아니다
  await expect(banner(page)).toBeVisible({ timeout: 8_000 });
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
  await server.scenario({ intakeDelay: 34_000, readingPolls: 0 });
  await send(page);
  await expect(banner(page)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("status").filter({ hasText: "서버가 아직 답하지 않았어요" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("status").filter({ hasText: "계속 안 되면 잠시 뒤에 다시 시도해 주세요." })).toBeVisible();
  await page.getByRole("status").filter({ hasText: "서버가 아직 답하지 않았어요" }).getByRole("button", { name: "닫기" }).click();
  await expect(page.getByRole("status").filter({ hasText: "서버가 아직 답하지 않았어요" })).toHaveCount(0);
  await page.waitForTimeout(2_500);
  await expect(page.getByRole("status").filter({ hasText: /서버(가 아직 답하지 않았어요| 응답이 늦어지고 있어요)/ })).toHaveCount(0);
});

test("계획을 읽는 동안 새 소식이 30초 없으면 읽는 화면이 「서버 소식이 한동안 없어요」라고 말하고, 읽기가 끝나면 사라진다", async ({ page, request }) => {
  test.setTimeout(90_000);
  const server = mockServer(request);
  await start(page);
  await server.scenario({ readingPolls: 999 });
  await send(page);
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);
  const note = page.getByRole("status").filter({ hasText: "서버 소식이 한동안 없어요" });
  await expect(page.getByRole("heading", { name: "계획을 확인하고 있어요", level: 1 })).toBeVisible();
  await page.waitForTimeout(20_000);
  await expect(note).toHaveCount(0);                                                                   // 20초는 아직이다
  await expect(note).toBeVisible({ timeout: 20_000 });
  await expect(note).toContainText("조금 더 기다리거나, 뒤로 가서 다시 보낼 수 있어요.");
  await expect(note).toContainText("초째");
  await server.scenario({ readingPolls: 0 });
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible({ timeout: 20_000 });
  await expect(note).toHaveCount(0);
});
