import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { answerCard, checkPlan, mockServer, start } from "./helpers";

/**
 * `[2026-10-06 사용자 지시 — 설문 화면 구현 인계 2단계]` 읽는 동안 묻는 질문(서버의 `questions[]`) — 카드 · 답 저장 · 밀기 · 저장 실패 · 읽기가 끝난 뒤 화면을 붙잡는 규칙(안 만졌으면 바로,
 * 남았으면 머무름, 다 답했거나 손도 안 댔으면 안내 + 5초 막대 뒤에 넘어감, 가만히 있으면 20초 경고). 테스트용 mock 서버로 도는 자동 시험이다(화면 반응을 본다 — 실서버 확인 아님).
 * `[2026-10-20 ST4F-665]` 질문 카드는 시작 설문(여행 취향 설문)의 카드다 — 서버 질문 묶음 "3"(누구와 + 인원 · 우선순위 · 실내외 · 여유)을 칩 · 인원 줄 · 분야 카드 · 두 줄로 그리고,
 * 카드를 다 채워야 켜지는 「다음」으로 저장한다. 계획서가 말한 칸은 묻지 않고 「계획서에서 읽었어요」, 읽기 뒤에 목록이 뒤로 한 번 늘고, 시작 설문 답은 첫 조회 전에 실어 다시 묻지 않는다.
 * 읽기는 mock 서버의 `readingPolls` 로 붙들어 두었다가(`HOLD`) `readingPolls: 0` 으로 끝낸다.
 * ☆계획 담기 화면의 「하루 일정의 여유」는 늘 정해진 채 등록에 실리므로(「처음부터 골라 두었어요」) 첫 조회 전에 여유가 실린다 — 그래서 여유 카드는 그 호출이 거절된 경우로 본다.
 */
// `[2026-10-16 사용자 결정 — CI 시간 줄이기 ③]` 화면의 기다림 계산(`Date.now` · `setTimeout` · `setInterval`)은 가짜 시계로 건너뛴다 —
//   「아직 안 넘어갔다 · 아직 안 떴다」는 시간을 건너뛴 뒤 화면이 다시 그려질 틈(0.3초)만 실제로 기다리고 본다.
const PLAN = "10/1 09:00 경복궁 관람";
const HOLD = 999;
const pager = (page: Page) => page.getByRole("region", { name: /^질문 \d개$/ });
const option = (page: Page, name: string) => pager(page).getByRole("button", { name, exact: true });
const next = (page: Page) => pager(page).getByRole("button", { name: /^(다음|답변 저장)$/ });
const bigButton = (page: Page, name: string) => page.getByRole("button", { name });
/** The start survey's own answers, as this browser keeps them (`onboarding-state.tsx`). */
const START_SURVEY = {
  complete: true, step: 3,
  answers: { party: "friends", partyOther: "", partySize: 3, priority: ["activity", "food"], details: { food: ["clean"], activity: ["HS", "NA", "VE"], mobility: [] },
    indoorDining: "indoor", indoorActivity: "any", pace: "relaxed", skipped: [] as number[] },
};

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

async function reading(page: Page, request: APIRequestContext, scenario: Record<string, unknown> = {}) {
  const server = mockServer(request);
  await server.scenario({ questions: "two", readingPolls: HOLD, ...scenario });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await checkPlan(page);
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);
  await expect.poll(async () => (await server.received("POST", "/survey")).length).toBe(1);          // 등록에 보낼 설문(여기서는 계획 담기 화면의 여유)을 먼저 싣는다
  return server;
}
const finishReading = (server: ReturnType<typeof mockServer>) => server.scenario({ readingPolls: 0 });
/** The answers the cards sent — after the one call that laid the registration's survey on the intake before its first read. */
const saved = async (server: ReturnType<typeof mockServer>) => (await server.received("POST", "/survey")).slice(1);
/** 「혼자」 → 「다음」, then the priorities: 음식 · 맛 → 「답변 저장」. */
async function answerBoth(page: Page) {
  await answerCard(page, "혼자");
  await expect(pager(page)).toContainText("2 / 2", { timeout: 3000 });
  await answerCard(page, "음식", "맛");
}

test("읽는 동안 시작 설문 카드가 서버의 문구 그대로 뜨고, 아래 단추는 꺼진 단추가 아니라 눌러 보면 이유를 말하는 「계획 읽는 중…」이다", async ({ page, request }) => {
  const server = await reading(page, request);
  await expect(page.getByText("기다리는 동안 여행 취향을 하나씩 여쭤볼게요.")).toBeVisible();
  await expect(pager(page)).toBeVisible();
  await expect(pager(page).getByRole("heading", { name: "누구와 함께 떠나나요?" })).toBeVisible();
  await expect(pager(page)).toContainText("함께 떠나는 사람을 하나 골라 주세요.");
  await expect(pager(page)).toContainText("1 / 2");
  for (const label of ["혼자", "연인", "친구", "가족", "기타"]) {
    const box = await option(page, label).boundingBox();
    expect(box!.height).toBeGreaterThanOrEqual(43.5); // 시작 설문 칩(46px) — 서브픽셀 반올림 오차를 허용한다.
  }
  await expect(next(page)).toBeDisabled();                                                             // 카드를 다 채워야 켜진다
  await expect(pager(page)).toContainText("좌우로 밀면 이전 · 다음 질문을 볼 수 있어요");
  await expect(pager(page).getByRole("button", { name: "이전 질문 보기" })).toBeDisabled();
  const wait = bigButton(page, "계획 읽는 중…");
  await expect(wait).toHaveAttribute("aria-disabled", "true");
  await expect(wait).toHaveAttribute("aria-busy", "true");
  await expect(page.getByText("로딩이 끝나면 단추가 켜져요.")).toBeVisible();
  await wait.click({ force: true });                                                                  // aria-disabled 단추는 시험 도구가 막는다 — 사람은 누를 수 있다
  await expect(page.getByText("아직 읽는 중이에요. 로딩이 끝나면 단추가 켜져요.")).toBeVisible();
  expect(await saved(server)).toHaveLength(0);
});

test("누구와는 시작 설문처럼 인원 줄이 붙고(친구 · 가족은 2명부터), 「다음」으로 인원과 함께 저장된 뒤 다음 질문으로 간다. 앞 질문으로 돌아가 고치면 덮어쓴다", async ({ page, request }) => {
  const server = await reading(page, request);
  await option(page, "친구").click();
  const sizes = pager(page).getByRole("group", { name: "인원" });
  await expect(sizes.getByRole("button", { name: "2명" })).toHaveAttribute("aria-pressed", "true");    // 친구는 2명부터
  await expect(sizes.getByRole("button", { name: "1명" })).toBeDisabled();
  await sizes.getByRole("button", { name: "3명" }).click();
  expect(await saved(server)).toHaveLength(0);                                                        // 고르기만 해서는 보내지 않는다
  await next(page).click();
  await expect(pager(page)).toContainText("저장했어요");
  expect((await saved(server))[0].body).toEqual({ answers: { party: "friends", party_size: "3" } });
  await expect(pager(page)).toContainText("2 / 2", { timeout: 3000 });
  await expect(pager(page).getByRole("heading", { name: "어떤 것을 더 중요하게 생각하나요?" })).toBeFocused();
  // 우선순위: 분야를 누른 순서가 순위, 활동 세부는 정확히 3개
  await option(page, "활동").click();
  for (const code of ["역사관광", "자연관광"]) await option(page, code).click();
  await expect(next(page)).toBeDisabled();
  await expect(pager(page)).toContainText("누른 순서대로 3개를 골라 주세요 · 2/3");
  await option(page, "문화관광").click();
  await expect(option(page, "쇼핑")).toBeDisabled();                                                  // 다 찼다
  await option(page, "이동").click();
  await expect(next(page)).toBeDisabled();                                                             // 이동도 세부가 하나는 있어야
  await option(page, "택시").click();
  await expect(next(page)).toHaveText("답변 저장");                                                    // 더 열린 질문이 없다
  await next(page).click();
  await expect.poll(async () => (await saved(server))[1]?.body).toEqual({ answers: { priority: { areas: ["activity", "mobility"], details: { activity: ["HS", "NA", "VE"], mobility: ["taxi"] } } } });
  await expect(page.getByText("질문에 모두 답했어요. 계획을 다 읽으면 계획 확인 화면으로 넘어가요.")).toBeVisible();
  // 앞 질문으로 돌아가 고친다 — 고른 것(인원까지)이 보이고, 다시 보내면 덮어쓴다
  await pager(page).getByRole("button", { name: "이전 질문 보기" }).click();
  await expect(pager(page)).toContainText("1 / 2");
  await expect(option(page, "친구")).toHaveAttribute("aria-pressed", "true");
  await expect(sizes.getByRole("button", { name: "3명" })).toHaveAttribute("aria-pressed", "true");
  await option(page, "혼자").click();
  await expect(sizes.getByRole("button", { name: "1명" })).toHaveAttribute("aria-pressed", "true");    // 혼자는 1명으로 정해진다
  await next(page).click();
  await expect.poll(async () => (await saved(server))[2]?.body).toEqual({ answers: { party: "alone", party_size: "1" } });
});

test("기타는 누구인지 적고 인원을 골라야 「다음」이 켜지고, 적은 글 그대로 저장된다. 답을 취소하면 비워지고 다시 입력할 수 있다", async ({ page, request }) => {
  const server = await reading(page, request);
  await option(page, "기타").click();
  const words = pager(page).getByLabel("누구와 함께 여행하는지 알려 주세요.");
  await words.fill("직장 동료");
  await expect(next(page)).toBeDisabled();                                                             // 기타는 인원을 골라야 한다
  await pager(page).getByRole("group", { name: "인원" }).getByRole("button", { name: "4명" }).click();
  await next(page).click();
  await expect.poll(async () => (await saved(server))[0]?.body).toEqual({ answers: { party: { custom: "직장 동료" }, party_size: "4" } });
  await expect(pager(page)).toContainText("2 / 2", { timeout: 3000 });
  await pager(page).getByRole("button", { name: "이전 질문 보기" }).click();
  await expect(words).toHaveValue("직장 동료");
  await pager(page).getByRole("button", { name: "답변 취소하고 다시 입력" }).click();
  await expect.poll(async () => (await saved(server))[1]?.body).toEqual({ answers: { party: null } });
  await expect(option(page, "기타")).toHaveAttribute("aria-pressed", "false");
  await expect(next(page)).toBeDisabled();
});

test("건너뛰기 없이 방향키 · 마우스로 밀기 · ‹ › 단추로 같은 질문을 볼 수 있다", async ({ page, request }) => {
  const server = await reading(page, request);
  await expect(pager(page).getByRole("button", { name: "이 질문 건너뛰기" })).toHaveCount(0);
  await expect(pager(page).getByRole("button", { name: "응답하지 않고 넘어가기" })).toHaveCount(0);
  await pager(page).getByRole("button", { name: "다음 질문 보기" }).click();
  await expect(pager(page)).toContainText("2 / 2");
  expect(await saved(server)).toHaveLength(0);                                                        // 넘겨 보기는 서버로 가지 않는다
  await pager(page).getByRole("button", { name: "이전 질문 보기" }).click();
  // 방향키
  await option(page, "혼자").focus();
  await page.keyboard.press("ArrowRight");
  await expect(pager(page)).toContainText("2 / 2");
  await page.keyboard.press("ArrowLeft");
  await expect(pager(page)).toContainText("1 / 2");
  // 밀기: 50px 넘게 옆으로 → 이동, 아래로 더 큰 움직임이면 이동 안 함, 짧으면 이동 안 함
  const slide = pager(page).locator('[aria-roledescription="slide"]');
  const box = (await slide.boundingBox())!;
  const y = box.y + 8, x = box.x + box.width / 2;
  const drag = async (dx: number, dy = 0) => { await page.mouse.move(x, y); await page.mouse.down(); await page.mouse.move(x + dx, y + dy, { steps: 4 }); await page.mouse.up(); };
  await drag(-30);
  await expect(pager(page)).toContainText("1 / 2");
  await drag(-80, 100);
  await expect(pager(page)).toContainText("1 / 2");
  await drag(-100);
  await expect(pager(page)).toContainText("2 / 2");
  await drag(100);
  await expect(pager(page)).toContainText("1 / 2");
  await pager(page).getByRole("button", { name: "다음 질문 보기" }).click();
  await expect(pager(page)).toContainText("2 / 2");
  await expect(pager(page).getByRole("button", { name: "다음 질문 보기" })).toBeDisabled();
});

test("답을 저장하지 못하면 카드는 고른 그대로 두고 「다시 시도하기」를 보이며 다음으로 넘어가지 않는다. 다시 시도해 서버가 받으면 이어진다", async ({ page, request }) => {
  const server = await reading(page, request, { surveySave: "fail" });
  await answerCard(page, "가족");
  const alert = pager(page).getByRole("alert");
  await expect(alert).toContainText("답을 저장하지 못했어요. 연결을 확인하고 다시 시도해 주세요.");
  await expect(option(page, "가족")).toHaveAttribute("aria-pressed", "true");
  await page.waitForTimeout(700);
  await expect(pager(page)).toContainText("1 / 2");                                                   // 넘어가지 않았다
  await expect(pager(page)).not.toContainText("저장했어요");
  await server.scenario({ surveySave: "ok" });
  await alert.getByRole("button", { name: "다시 시도하기" }).click();
  await expect(pager(page)).toContainText("저장했어요");
  await expect(alert).toHaveCount(0);
  await expect(pager(page)).toContainText("2 / 2", { timeout: 3000 });
  expect((await saved(server)).map((entry) => entry.body)).toEqual([{ answers: { party: "family", party_size: "2" } }, { answers: { party: "family", party_size: "2" } }]);
});

test("질문이 나오면 거기로 초점이 가고 시선을 끄는 움직임이 한 번 나온다", async ({ page, request }) => {
  await reading(page, request);
  await expect(pager(page)).toBeVisible();
  await expect(pager(page).getByRole("heading", { name: "누구와 함께 떠나나요?" })).toBeFocused();
  await expect(pager(page)).toHaveAttribute("data-attention", "true");                                    // 아래에서 올라오며 테두리 고리가 두 번 퍼진다
  await expect(pager(page)).not.toHaveAttribute("data-attention", "true", { timeout: 5000 });             // 끝나면 사라진다
});

test("한 번도 만지지 않았어도 읽기가 끝나는 대로 곧장 넘어가지 않는다 — 「계획을 다 읽었어요」 안내를 보이고 5초를 기다린 뒤 계획 확인 화면으로 간다", async ({ page, request }) => {
  const server = await reading(page, request);
  await expect(pager(page)).toBeVisible();
  await page.clock.install();
  await finishReading(server);
  await expect(page.getByText("계획을 다 읽었어요", { exact: true }).first()).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("5초 뒤에 계획 확인 화면으로 넘어가요.")).toBeVisible();
  await expect(page.getByText("남은 질문 2개는 지금 답해도 돼요.")).toBeVisible();
  await page.clock.fastForward(2_500);
  await page.waitForTimeout(300);
  await expect(pager(page)).toBeVisible();                                                            // 아직 5초가 안 됐다 — 질문이 그대로 있다
  await page.clock.fastForward(3_000);
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible({ timeout: 15_000 });  // 5초가 지나자 넘어간다
  await expect(pager(page)).toHaveCount(0);
});

test("5초 기다리는 동안 질문을 건드리면 저절로 넘어가지 않고 머문다", async ({ page, request }) => {
  const server = await reading(page, request);
  await page.clock.install();
  await finishReading(server);
  await expect(page.getByText("5초 뒤에 계획 확인 화면으로 넘어가요.")).toBeVisible({ timeout: 15_000 });
  await option(page, "혼자").click();                                                                  // 질문을 만진다
  await expect(page.getByText("5초 뒤에 계획 확인 화면으로 넘어가요.")).toHaveCount(0);
  await page.clock.fastForward(6_000);
  await page.waitForTimeout(300);
  await expect(pager(page)).toBeVisible();
  await expect(bigButton(page, "읽어 온 계획 확인하기")).toBeEnabled();
});

test("만졌고 열린 질문이 남아 있으면 읽기가 끝나도 화면에 머물고, 「읽어 온 계획 확인하기」를 누르면 계획 확인으로 간다", async ({ page, request }) => {
  const server = await reading(page, request);
  await answerCard(page, "혼자");
  await expect(pager(page)).toContainText("2 / 2", { timeout: 3000 });
  await page.clock.install();
  await finishReading(server);
  await expect(page.getByText("계획을 다 읽었어요")).toBeVisible({ timeout: 15_000 });
  await expect(pager(page)).toBeVisible();                                                           // 질문을 빼앗지 않는다
  const go = bigButton(page, "읽어 온 계획 확인하기");
  await expect(go).toBeEnabled();
  await expect(page.getByText("남은 질문 1개는 다음에 계획을 읽을 때 다시 답할 수 있어요.")).toBeVisible();
  await page.clock.fastForward(1_500);
  await page.waitForTimeout(300);
  await expect(pager(page)).toBeVisible();                                                           // 저절로 넘어가지 않는다
  await go.click();
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible({ timeout: 15_000 });
  await expect(pager(page)).toHaveCount(0);
});

test("읽는 중에 다 답했으면 읽기가 끝난 뒤 5초 막대를 보이고 계획 확인으로 간다. 질문을 만지면 멈추고, 「자동으로 넘어가지 않기」를 누르면 더 이상 저절로 가지 않는다", async ({ page, request }) => {
  const server = await reading(page, request);
  await answerBoth(page);
  await page.clock.install();
  await finishReading(server);
  const line = page.getByText("질문에 모두 답했어요", { exact: true });
  await expect(line).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("5초 뒤에 계획 확인 화면으로 넘어가요.")).toBeVisible();
  // 질문 카드를 만지면 막대가 멈춘다
  await pager(page).getByRole("button", { name: "이전 질문 보기" }).click();
  await expect(line).toHaveCount(0);
  await expect(bigButton(page, "읽어 온 계획 확인하기")).toBeEnabled();
  await page.clock.fastForward(5_500);
  await page.waitForTimeout(300);
  await expect(pager(page)).toBeVisible();
  await expect(page.getByText("질문에 모두 답했어요. 아래 단추를 누르면 계획 확인 화면으로 가요.")).toBeVisible();
  await bigButton(page, "읽어 온 계획 확인하기").click();
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible({ timeout: 15_000 });
});

test("「자동으로 넘어가지 않기」를 누르면 다 답했어도 저절로 계획 확인으로 가지 않고 머문다", async ({ page, request }) => {
  const server = await reading(page, request);
  await answerBoth(page);
  await page.clock.install();
  await finishReading(server);
  await expect(page.getByText("질문에 모두 답했어요", { exact: true })).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: "자동으로 넘어가지 않기" }).click();
  await expect(page.getByText("이제 자동으로 넘어가지 않아요.")).toBeVisible();
  await page.clock.fastForward(6_000);
  await page.waitForTimeout(300);
  await expect(pager(page)).toBeVisible();
});

test("다 답하고 읽기가 끝나면 5초 막대 뒤에 저절로 계획 확인으로 간다", async ({ page, request }) => {
  const server = await reading(page, request);
  await answerBoth(page);
  await finishReading(server);
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible({ timeout: 20_000 });
});

test("읽기가 끝난 뒤 30초 무응답 경고의 단일 「계속 답하기」로 자동 넘김을 멈추고 답변을 이어간다", async ({ page, request }) => {
  test.setTimeout(150_000);
  const server = await reading(page, request);
  await answerCard(page, "혼자");
  await expect(pager(page)).toContainText("2 / 2", { timeout: 3000 });
  await page.clock.install();
  await finishReading(server);
  await expect(bigButton(page, "읽어 온 계획 확인하기")).toBeEnabled({ timeout: 15_000 });
  const warning = page.getByRole("alertdialog");
  await page.clock.fastForward(30100);
  await expect(warning).toBeVisible();
  await expect(warning).toContainText("아직 보고 계신가요?");
  await expect(warning.getByRole("button", { name: "계속 답하기" })).toBeFocused();
  const first = await warning.locator("p").first().textContent();
  await expect(warning.getByRole("button")).toHaveCount(1);
  await page.clock.runFor(3000);
  expect(Number(await warning.locator("p").first().textContent())).toBeLessThan(Number(first));
  await warning.getByRole("button", { name: "계속 답하기" }).click();
  await expect(warning).toHaveCount(0);
  await expect(pager(page)).toBeVisible();
  await page.clock.runFor(61000);
  await expect(warning).toHaveCount(0);
  await expect(pager(page)).toBeVisible();
  await pager(page).getByRole("button", { name: "이전 질문 보기" }).click();
  await expect(option(page, "혼자")).toHaveAttribute("aria-pressed", "true");
});

test("계획서가 말한 칸은 묻지 않고 「계획서에서 읽었어요」를 보이며, 읽기 뒤 목록은 뒤로 한 번 늘어난다(실내외 · 여유). 먼저 싣는 호출이 거절되면 서버가 평소처럼 다 묻는다", async ({ page, request }) => {
  // 첫 조회 전에 싣는 호출을 서버가 거절한다 — 웹은 다시 보내지 않고, 서버는 아무것도 받지 않았으니 여유까지 넷을 묻는다
  const server = await reading(page, request, { questions: "four", questionsRead: "on", questionsPhase2After: 2, surveySave: "fail" });
  await server.scenario({ surveySave: "ok" });
  await expect(page.getByRole("region", { name: "질문 4개" })).toBeVisible({ timeout: 10_000 });   // 첫 목록 둘 뒤에 둘이 붙는다
  await expect(pager(page)).toContainText("1 / 4");                                                  // 보던 질문(답 없음)은 그대로
  await expect(pager(page).getByRole("heading", { name: "누구와 함께 떠나나요?" })).toBeVisible();
  await answerCard(page, "연인");
  await expect(pager(page)).toContainText("2 / 4", { timeout: 3000 });
  // 이동 세부는 계획서가 말했다 — 칩 대신 읽은 말, 고르지 않아도 된다
  await option(page, "이동").click();
  const mobility = pager(page).getByRole("group", { name: "이동 세부 항목" });
  await expect(mobility).toContainText("계획서에서 읽었어요: 택시 (“웬만하면 택시로”)");
  await expect(mobility.getByRole("button")).toHaveCount(0);
  await next(page).click();
  await expect.poll(async () => (await saved(server))[1]?.body).toEqual({ answers: { priority: { areas: ["mobility"], details: {} } } });
  await expect(pager(page)).toContainText("3 / 4", { timeout: 3000 });
  // 실내외: 액티비티 칸은 계획서가 말했다 — 식당만 고른다
  await expect(pager(page).getByRole("heading", { name: "실내와 실외 중 어디가 좋으세요?" })).toBeVisible();
  await expect(pager(page)).toContainText("계획서에서 읽었어요: 실내 (“비 오면 실내”)");
  await expect(pager(page).getByRole("button", { name: "실내", exact: true })).toHaveCount(1);       // 식당 줄 하나뿐
  await answerCard(page, "실외");
  await expect.poll(async () => (await saved(server))[2]?.body).toEqual({ answers: { indoor_outdoor: { dining: "outdoor" } } });
  await expect(pager(page)).toContainText("4 / 4", { timeout: 3000 });
  await expect(next(page)).toBeDisabled();
  await answerCard(page, "꽉 차게");
  await expect.poll(async () => (await saved(server))[3]?.body).toEqual({ answers: { pace: "packed" } });
  await expect(page.getByText("질문에 모두 답했어요. 계획을 다 읽으면 계획 확인 화면으로 넘어가요.")).toBeVisible();
});

test("첫 목록에 다 답하고 기다리던 중 읽기가 끝나 질문이 뒤에 붙으면, 새 질문으로 넘어가 화면에 머문다(여유는 계획 담기 화면에서 실려 묻지 않는다)", async ({ page, request }) => {
  const server = await reading(page, request, { questions: "four" });
  expect((await server.received("POST", "/survey"))[0].body).toEqual({ answers: { pace: "moderate" } });
  await answerBoth(page);
  await expect(page.getByText("질문에 모두 답했어요. 계획을 다 읽으면 계획 확인 화면으로 넘어가요.")).toBeVisible();
  await finishReading(server);
  await expect(page.getByRole("region", { name: "질문 3개" })).toBeVisible({ timeout: 15_000 });
  await expect(pager(page)).toContainText("3 / 3");
  await expect(pager(page).getByRole("heading", { name: "실내와 실외 중 어디가 좋으세요?" })).toBeVisible();
  await expect(bigButton(page, "읽어 온 계획 확인하기")).toBeEnabled();
  await pager(page).getByRole("button", { name: "실내", exact: true }).first().click();                 // 식당 줄
  await expect(next(page)).toBeDisabled();                                                             // 액티비티 줄도 골라야
  await pager(page).getByRole("button", { name: "상관없음", exact: true }).nth(1).click();              // 액티비티 줄
  await next(page).click();
  await expect.poll(async () => (await saved(server))[2]?.body).toEqual({ answers: { indoor_outdoor: { dining: "indoor", activity: "any" } } });
  await expect(page.getByRole("heading", { name: "여행할 때 어느 정도 여유가 좋으세요?" })).toHaveCount(0);
});

test("시작 설문에서 답한 것은 첫 조회 전에 실어 보내 로딩에서 다시 묻지 않는다(인원 포함 · 일정이 꼬이면은 빼고)", async ({ page, request }) => {
  await page.addInitScript((value) => localStorage.setItem("tripilot.web.onboarding.v2", value), JSON.stringify(START_SURVEY));
  const server = await reading(page, request, { questions: "four" });
  expect((await server.received("POST", "/survey"))[0].body).toEqual({ answers: {
    party: "friends", party_size: "3", priority: { areas: ["activity", "food"], details: { activity: ["HS", "NA", "VE"], food: ["clean"] } },
    indoor_outdoor: { dining: "indoor", activity: "any" }, pace: "relaxed",
  } });
  const log = await server.log();
  const laid = log.findIndex((entry) => entry.method === "POST" && entry.path.endsWith("/survey"));
  const firstRead = log.findIndex((entry) => entry.method === "GET" && /\/v1\/web\/trip-intakes\/[^/]+$/.test(entry.path));
  expect(laid).toBeGreaterThanOrEqual(0);
  expect(firstRead).toBeGreaterThan(laid);                                                            // 실은 뒤에 처음 읽는다 — 서버가 첫 조회 때 목록을 정한다
  await expect(page.getByRole("heading", { name: "계획을 확인하고 있어요", level: 1 })).toBeVisible();
  await expect(pager(page)).toHaveCount(0);                                                          // 넷 다 답했으니 묻지 않는다
  await finishReading(server);
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible({ timeout: 15_000 });
  await expect(pager(page)).toHaveCount(0);
});

test("시작 설문에서 건너뛴 질문만 로딩에서 묻는다", async ({ page, request }) => {
  const survey = { ...START_SURVEY, answers: { ...START_SURVEY.answers, indoorDining: "", indoorActivity: "", skipped: [2] } };
  await page.addInitScript((value) => localStorage.setItem("tripilot.web.onboarding.v2", value), JSON.stringify(survey));
  const server = await reading(page, request, { questions: "four" });
  expect(Object.keys(((await server.received("POST", "/survey"))[0].body?.answers ?? {}) as Record<string, unknown>).sort()).toEqual(["pace", "party", "party_size", "priority"]);
  await expect(pager(page)).toHaveCount(0);
  await finishReading(server);
  await expect(page.getByRole("region", { name: "질문 1개" })).toBeVisible({ timeout: 15_000 });
  await expect(pager(page).getByRole("heading", { name: "실내와 실외 중 어디가 좋으세요?" })).toBeVisible();
});

test("모르는 종류의 질문은 그 질문만 건너뛰고 나머지는 그린다", async ({ page, request }) => {
  await reading(page, request, { questions: "unknown_kind" });
  await expect(pager(page)).toContainText("1 / 2");                                                   // 셋 중 둘
  await expect(page.getByText("미래의 질문")).toHaveCount(0);
});

test("질문 목록이 없는 옛 서버에서는 아무것도 묻지 않고 읽는 화면은 전과 같다", async ({ page, request }) => {
  await reading(page, request, { questions: "none" });
  await expect(page.getByRole("heading", { name: "계획을 확인하고 있어요", level: 1 })).toBeVisible();
  await expect(pager(page)).toHaveCount(0);
  await expect(page.getByText("계획 읽는 중…")).toHaveCount(0);
  await expect(page.getByText("기다리는 동안 여행 취향을 하나씩 여쭤볼게요.")).toHaveCount(0);
});

test("영어 화면에서는 시작 설문의 영어를 질문 · 선택지 번호로 쓴다", async ({ page, request }) => {
  await page.addInitScript(() => localStorage.setItem("tripilot.web.settings.v1", JSON.stringify({ language: "en" })));
  const server = mockServer(request);
  await server.scenario({ questions: "two", readingPolls: HOLD });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("Your travel plan").fill(PLAN);
  await page.getByRole("button", { name: "Check my plan" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Turn on and go on" }).click();
  const questions = page.getByRole("region", { name: "2 questions" });
  await expect(questions).toBeVisible();
  await expect(page.getByRole("heading", { name: "Who’s coming along?" })).toBeVisible();
  for (const name of ["Solo", "Partner", "Friends", "Family", "Other"]) await expect(questions.getByRole("button", { name, exact: true })).toBeVisible();
  await expect(questions.getByRole("button", { name: "Next", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Reading your plan…" })).toHaveAttribute("aria-disabled", "true");
});

test("좁은 화면(375×812)에서도 머리 · 질문 · 읽는 줄 · 아래 단추가 화면 안에 들어가고 가로로 넘치지 않는다", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await reading(page, request);
  await expect(pager(page)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const footer = await bigButton(page, "계획 읽는 중…").boundingBox();
  expect(footer!.y + footer!.height).toBeLessThanOrEqual(812);
  expect(footer!.height).toBeGreaterThanOrEqual(44);
  for (const name of ["이전 질문 보기", "다음 질문 보기"]) {
    const box = await pager(page).getByRole("button", { name }).boundingBox();
    expect(box!.width).toBeGreaterThanOrEqual(43.5);
    expect(box!.height).toBeGreaterThanOrEqual(43.5); // 서브픽셀 반올림 오차를 허용한다.
  }
  // 우선순위 카드(가장 큰 카드)도 가로로 넘치지 않는다
  await pager(page).getByRole("button", { name: "다음 질문 보기" }).click();
  await option(page, "활동").click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
