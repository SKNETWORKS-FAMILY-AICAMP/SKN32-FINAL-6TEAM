import { expect, test, type Page } from "@playwright/test";
import { checkPlan, mockServer, start } from "./helpers";

/**
 * `[2026-10-21 사용자 결정 — P6 해석 확인 질문]` 계획서의 한 줄을 읽기 AI 가 일정이 아닌 것(빈 시간 등)으로 읽었으면, 첫 검사 재생이 그 줄의 시각에 닿을 때 카드 없는 질문 칸으로 멈춰 묻는다
 * (목업 `mockups/tripilot-plan-check-interpretation.html`) — 테스트용 모방 서버로 도는 자동 시험(실제 서버 아님).
 * 모방 서버의 `board: "calm"` + `interpretations: "on"`: 고칠 것이 없는 세 일정(경복궁 09:00 · 올리브영 광화문점 11:00 · 광장시장 12:30) 뒤, 5번째 줄 「14시~16시 정도 시간이 비는데」를
 * AI 는 빈 시간으로, 규칙은 일정 「정도」(오타 고침으로 「정돈 대학로본점」)로 읽었다 — 그 일정은 빠진 채로 묻는다.
 */
const INTAKE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const question = (page: Page) => page.locator("[data-stop-question]");
const banner = (page: Page) => page.locator("[data-stop-banner]");
const slot = (page: Page) => page.locator('li[data-type="ask"]');
const answers = async (server: ReturnType<typeof mockServer>) => (await server.received("POST", `${INTAKE}/interpretations`)).map((entry) => entry.body);

async function asked(page: Page, request: Parameters<typeof mockServer>[0], change: Record<string, unknown> = {}) {
  const server = mockServer(request);
  await server.reset();
  await server.scenario({ review: "on", board: "calm", interpretations: "on", intakeEvents: "on", readingPolls: 1, ...change });
  await start(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill("10/1 09:00 경복궁 관람");
  await checkPlan(page);
  await expect(question(page)).toBeVisible({ timeout: 40_000 });
  return server;
}

test("앞 일정을 다 그린 뒤 그 줄의 시각(14:00)에서 카드 없는 질문 칸으로 멈춘다 — 서버 문장 그대로, 1안에 「추천」, 「직접 선택」, 삭제 없음", async ({ page, request }) => {
  await asked(page, request);
  await expect(banner(page)).toContainText("이 줄을 어떻게 읽을지 먼저 골라 주세요");
  await expect(banner(page)).toContainText("고르면 확인을 마쳐요");
  await expect(slot(page)).toHaveAttribute("data-stop-focus", "true");
  await expect(slot(page)).toContainText("14:00");
  await expect(question(page)).toContainText("읽은 뜻");
  await expect(question(page)).toContainText("계획서의 「14시~16시 정도 시간이 비는데」를 어떻게 이해할까요?");
  const first = question(page).getByRole("button", { name: /14:00~16:00 빈 시간/ });
  await expect(first).toContainText("추천");
  await expect(first).toContainText("이유: 읽기 AI 가 「14시~16시 정도 시간이 비는데」를 빈 시간으로 읽었어요");
  await expect(first).toContainText("고르면: 일정에 넣지 않고 14:00~16:00 빈 시간으로 둬요");
  await expect(question(page).getByRole("button", { name: /「정돈 대학로본점」 14:00 일정/ })).toContainText("고르면: 14:00 일정으로 넣고 영업시간 · 이동을 확인해요");
  await expect(question(page).getByRole("button", { name: /「정도」 이름 그대로 찾기/ })).toBeVisible();
  await expect(question(page).getByRole("button", { name: "직접 선택" })).toBeVisible();
  await expect(question(page).getByRole("button", { name: "삭제" })).toHaveCount(0);
  // 앞 일정은 다 그렸고(흐리게), 검사는 아직 끝나지 않았다
  await expect(page.getByRole("article", { name: "광장시장", exact: true })).toBeVisible();
  await expect(page.locator('main[data-stage="done"]')).toHaveCount(0);
  await expect(page.locator("[data-register-bar]")).toHaveCount(0);
});

test("1안(빈 시간)을 고르면 답만 저장하고 질문 칸이 사라지며 검사를 마친다 — 그 줄은 일정이 되지 않는다", async ({ page, request }) => {
  const server = await asked(page, request);
  await question(page).getByRole("button", { name: /14:00~16:00 빈 시간/ }).click();
  await expect(page.locator('main[data-stage="done"]')).toBeVisible({ timeout: 15_000 });
  expect(await answers(server)).toEqual([{ revision: 1, answers: { "q-0-5": "reading" } }]);
  await expect(slot(page)).toHaveCount(0);
  await expect(page.getByRole("article", { name: "정도", exact: true })).toHaveCount(0);
  await expect(page.locator("[data-register-bar]")).toBeVisible();                       // 지켜본 검사가 통과했으니 5초 자동 등록 막대
  await page.locator("[data-register-bar]").getByRole("button", { name: "자동으로 넘어가지 않기" }).click();
  expect(await server.received("POST", "/edits")).toHaveLength(0);
});

test("2안(가게 일정)을 고르면 그 자리(14:00)에 일정이 되살아나 확인한 뒤 검사를 마친다", async ({ page, request }) => {
  const server = await asked(page, request);
  await question(page).getByRole("button", { name: /「정돈 대학로본점」 14:00 일정/ }).click();
  const back = page.getByRole("article", { name: "정도", exact: true });
  await expect(back).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('main[data-stage="done"]')).toBeVisible({ timeout: 15_000 });
  expect(await answers(server)).toEqual([{ revision: 1, answers: { "q-0-5": "item" } }]);
  await expect(page.locator('li[data-entry-id="0-3"]')).toHaveAttribute("data-start", "14:00");
  await expect(slot(page)).toHaveCount(0);
});

test("「「정도」 이름 그대로 찾기」는 일정을 되살린 뒤 그 일정의 바꾸기 화면을 검색어 「정도」로 열고, 고르면 그 자리에서 다시 확인한다", async ({ page, request }) => {
  const server = await asked(page, request);
  await question(page).getByRole("button", { name: /「정도」 이름 그대로 찾기/ }).click();
  await expect(page.getByPlaceholder("정도 대신 찾을 장소")).toHaveValue("정도", { timeout: 15_000 });
  expect(await answers(server)).toEqual([{ revision: 1, answers: { "q-0-5": "item_search" } }]);
  await page.getByRole("button", { name: /올리브영 명동 플래그십/ }).click();                       // 검색 결과(모방 서버는 무엇을 찾아도 이 한 곳)
  await page.getByRole("button", { name: "이 장소로 바꾸기" }).first().click();
  await expect.poll(async () => (await server.received("POST", "/edits")).length).toBe(1);
  const [pick] = await server.received("POST", "/edits");
  expect(pick.body).not.toHaveProperty("check");                                         // 흐름 안 고르기는 검사와 함께(「다시 제출」 없음)
  await expect(page.locator('main[data-stage="done"]')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("button", { name: "다시 제출" })).toHaveCount(0);
});

test("「직접 선택」도 일정을 되살리고(장소를 고르는 안으로) 바꾸기 화면을 검색어 「정도」로 연다", async ({ page, request }) => {
  const server = await asked(page, request);
  await question(page).getByRole("button", { name: "직접 선택" }).click();
  await expect(page.getByPlaceholder("정도 대신 찾을 장소")).toHaveValue("정도", { timeout: 15_000 });
  expect(await answers(server)).toEqual([{ revision: 1, answers: { "q-0-5": "item_search" } }]);
});

test("답이 거절되면 남는 경고로 말하고 질문 칸이 다시 열린다", async ({ page, request }) => {
  await asked(page, request, { fail: "interpretations" });
  await question(page).getByRole("button", { name: /14:00~16:00 빈 시간/ }).click();
  await expect(page.getByText(/요청을 처리하지 못했어요/)).toBeVisible();
  await expect(question(page)).toBeVisible();
  await expect(banner(page)).toContainText("이 줄을 어떻게 읽을지 먼저 골라 주세요");
});

test("검사가 끝난 접수를 다시 열면 묻지 않고 결과 화면 — 서버가 적용해 둔 1안(일정 없음) 그대로", async ({ page, request }) => {
  const server = mockServer(request);
  await server.reset();
  await server.scenario({ review: "on", board: "calm", interpretations: "on", readingPolls: 0 });
  await start(page);
  await page.goto(`/intakes/${INTAKE}`);
  await expect(page.locator('main[data-stage="done"]')).toBeVisible({ timeout: 15_000 });
  await expect(question(page)).toHaveCount(0);
  await expect(page.getByRole("article", { name: "정도", exact: true })).toHaveCount(0);
  expect(await answers(server)).toHaveLength(0);
});

test("「애니메이션 건너뛰기」여도 그 줄의 자리에서 멈춰 묻는다", async ({ page, request }) => {
  await page.addInitScript(() => localStorage.setItem("tripilot.web.settings.v1", JSON.stringify({ language: "ko", skipAnimation: true })));
  await asked(page, request);
  await expect(slot(page)).toHaveAttribute("data-stop-focus", "true");
  await expect(page.getByRole("article", { name: "광장시장", exact: true })).toBeVisible();
});
