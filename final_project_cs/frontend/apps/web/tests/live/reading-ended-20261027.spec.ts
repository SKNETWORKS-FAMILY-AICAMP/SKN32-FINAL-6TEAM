import { expect, test } from "@playwright/test";
import { checkPlan, mockServer, start } from "./helpers";

/**
 * `[2026-10-27 웹 전수검사]` 읽기 화면의 진행 표시 · 접수 다시 읽기(GET) 횟수 — 모바일 폭(390×844).
 * ①읽기는 끝났는데(`review`) 서버 검사가 없는(`review: null` · `review_error`) 접수: 「계획을 다 읽었어요」 아래 막대가 「일정 읽기 … n초째」로 계속 세지 않는다.
 * ②읽는 동안 3초 생존 신호(`beat`)마다 접수 GET 을 보내지 않는다(x600 2026-10-26: 접수 하나에 10분 110회).
 * 테스트용 mock 서버로 도는 자동 시험이다(화면 반응을 본다 — 실서버 확인 아님).
 */
const PLAN = "10/1 09:00 경복궁 관람";
const HOLD = 999;

test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

test("읽는 동안 생존 신호마다 접수를 다시 읽지 않고, 검사 없이 끝난 읽기의 막대는 초를 세지 않는다 (모바일 폭)", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ questions: "two", readingPolls: HOLD, review: "off" });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await checkPlan(page);
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);
  const pager = page.getByRole("region", { name: /^질문 \d개$/ });
  await expect(pager.getByRole("heading", { name: "누구와 함께 떠나나요?" })).toBeVisible();

  // ② 읽는 6초 동안(mock 의 beat 0.3초 간격 = 약 20번) 접수 GET 은 연결 첫 신호 · 단계 변화 때만.
  const intakeGets = async () => (await server.log()).filter((entry) => entry.method === "GET" && /\/v1\/web\/trip-intakes\/[^/]+$/.test(entry.path)).length;
  const before = await intakeGets();
  await page.waitForTimeout(6_000);
  const during = await intakeGets() - before;
  test.info().annotations.push({ type: "intake GETs in 6 s", description: String(during) });
  console.log(`intake GETs in 6 s while reading: ${during}`);
  expect(during).toBeLessThanOrEqual(2);

  await pager.getByRole("button", { name: "친구", exact: true }).click();
  await server.scenario({ readingPolls: 0 });
  await expect(page.getByText("계획을 다 읽었어요")).toBeVisible();
  // ① 붙잡힌 화면에서 9초(8초 넘으면 「n초째」) 기다려도 막대는 끝난 상태다.
  await page.waitForTimeout(9_000);
  const bar = page.getByRole("progressbar", { name: "계획 확인 진행" });
  await expect(bar).toHaveAttribute("aria-valuetext", /^읽기 완료 · 확인 결과 없음/);
  await expect(page.getByText(/\d+초째/)).toHaveCount(0);
  await page.screenshot({ path: test.info().outputPath("reading-ended-review-null.png"), fullPage: false });
});
