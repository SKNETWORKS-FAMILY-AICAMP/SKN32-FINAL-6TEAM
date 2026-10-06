import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { checkPlan, mockServer, start } from "./helpers";

/**
 * `[2026-10-06 사용자 지시 — 설문 화면 구현 인계 2단계]` 읽는 동안 묻는 질문(서버의 `questions[]`) — 카드 · 답 저장 · 건너뛰기 · 밀기 · 저장 실패 · 읽기가 끝난 뒤 화면을 붙잡는 규칙(안 만졌으면 바로,
 * 남았으면 머무름, 다 답했으면 3초 막대, 가만히 있으면 20초 경고). 테스트용 mock 서버로 도는 자동 시험이다(화면 반응을 본다 — 실서버 확인 아님).
 * 읽기는 mock 서버의 `readingPolls` 로 붙들어 두었다가(`HOLD`) `readingPolls: 0` 으로 끝낸다.
 */
const PLAN = "10/1 09:00 경복궁 관람";
const HOLD = 999;
const pager = (page: Page) => page.getByRole("region", { name: /^질문 \d개$/ });
const option = (page: Page, name: string) => pager(page).getByRole("button", { name, exact: true });
const bigButton = (page: Page, name: string) => page.getByRole("button", { name });

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

async function reading(page: Page, request: APIRequestContext, scenario: Record<string, unknown> = {}) {
  const server = mockServer(request);
  await server.scenario({ questions: "two", readingPolls: HOLD, ...scenario });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await checkPlan(page);
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);
  return server;
}
const finishReading = (server: ReturnType<typeof mockServer>) => server.scenario({ readingPolls: 0 });
const saved = (server: ReturnType<typeof mockServer>) => server.received("POST", "/survey");

test("읽는 동안 질문 카드가 서버의 문구 그대로 뜨고, 아래 단추는 꺼진 단추가 아니라 눌러 보면 이유를 말하는 「계획 읽는 중…」이다", async ({ page, request }) => {
  const server = await reading(page, request);
  await expect(page.getByText("기다리는 동안 하나씩 여쭤볼게요. 건너뛰어도 괜찮아요.")).toBeVisible();
  await expect(pager(page)).toBeVisible();
  await expect(pager(page).getByRole("heading", { name: "이동은 주로 어떻게 하세요?" })).toBeVisible();
  await expect(pager(page)).toContainText("계획서만으로는 이동 방법을 알 수 없어서 여쭤요");
  await expect(pager(page)).toContainText("1 / 2");
  for (const label of ["대중교통", "택시", "걷기 위주"]) {
    const box = await option(page, label).boundingBox();
    expect(box!.height).toBeGreaterThanOrEqual(48);
  }
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

test("답하면 그 문항만 바로 저장되고(「저장했어요」), 잠시 뒤 다음 열린 질문으로 가며 초점이 그 제목에 간다. 앞 질문으로 돌아가 고치면 덮어쓴다", async ({ page, request }) => {
  const server = await reading(page, request);
  await option(page, "택시").click();
  await expect(option(page, "택시")).toHaveAttribute("aria-pressed", "true");
  await expect(pager(page)).toContainText("저장했어요");
  const [first] = await saved(server);
  expect(first.body).toEqual({ answers: { preferred_mobility: "taxi" } });
  await expect(pager(page)).toContainText("2 / 2", { timeout: 3000 });
  await expect(pager(page).getByRole("heading", { name: /대체할 곳은/ })).toBeFocused();
  await option(page, "이동이 편한 곳").click();
  expect((await saved(server))[1].body).toEqual({ answers: { priority: "mobility" } });
  // 다 답했다: 다음 열린 질문이 없으니 그대로 있고, 아래 줄이 다음에 일어날 일을 말한다
  await expect(page.getByText("질문에 모두 답했어요. 계획을 다 읽으면 계획 확인 화면으로 넘어가요.")).toBeVisible();
  // 앞 질문으로 돌아가 고친다 — 고른 것이 보이고, 다시 누르면 덮어쓴다
  await pager(page).getByRole("button", { name: "이전 질문 보기" }).click();
  await expect(pager(page)).toContainText("1 / 2");
  await expect(option(page, "택시")).toHaveAttribute("aria-pressed", "true");
  await option(page, "걷기 위주").click();
  await expect(option(page, "걷기 위주")).toHaveAttribute("aria-pressed", "true");
  expect((await saved(server))[2].body).toEqual({ answers: { preferred_mobility: "walk" } });
});

test("건너뛴 질문은 알려 주고, 돌아와 답할 수 있다. 방향키 · 마우스로 밀기 · ‹ › 단추가 같은 이동이다", async ({ page, request }) => {
  const server = await reading(page, request);
  await pager(page).getByRole("button", { name: "이 질문 건너뛰기" }).click();
  await expect(pager(page)).toContainText("2 / 2");
  expect(await saved(server)).toHaveLength(0);                                                        // 건너뛰기는 서버로 가지 않는다
  await pager(page).getByRole("button", { name: "이전 질문 보기" }).click();
  await expect(pager(page)).toContainText("건너뛰었어요. 밀어서 돌아와 다시 답할 수 있어요.");
  // 방향키
  await option(page, "택시").focus();
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

test("답을 저장하지 못하면 고른 것은 그대로 두고 「다시 시도하기」를 보이며 다음으로 넘어가지 않는다. 다시 시도해 서버가 받으면 이어진다", async ({ page, request }) => {
  const server = await reading(page, request, { surveySave: "fail" });
  await option(page, "대중교통").click();
  const alert = pager(page).getByRole("alert");
  await expect(alert).toContainText("답을 저장하지 못했어요. 연결을 확인하고 다시 시도해 주세요.");
  await expect(option(page, "대중교통")).toHaveAttribute("aria-pressed", "true");
  await page.waitForTimeout(700);
  await expect(pager(page)).toContainText("1 / 2");                                                   // 넘어가지 않았다
  await expect(pager(page)).not.toContainText("저장했어요");
  await server.scenario({ surveySave: "ok" });
  await alert.getByRole("button", { name: "다시 시도하기" }).click();
  await expect(pager(page)).toContainText("저장했어요");
  await expect(alert).toHaveCount(0);
  await expect(pager(page)).toContainText("2 / 2", { timeout: 3000 });
  expect((await saved(server)).map((entry) => entry.body)).toEqual([{ answers: { preferred_mobility: "public" } }, { answers: { preferred_mobility: "public" } }]);
});

test("한 번도 만지지 않았으면 읽기가 끝나는 대로 곧장 계획 확인 화면으로 간다(질문 카드는 사라진다)", async ({ page, request }) => {
  const server = await reading(page, request);
  await expect(pager(page)).toBeVisible();
  await finishReading(server);
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible({ timeout: 15_000 });
  await expect(pager(page)).toHaveCount(0);
});

test("만졌고 열린 질문이 남아 있으면 읽기가 끝나도 화면에 머물고, 「읽어 온 계획 확인하기」를 누르면 계획 확인으로 간다", async ({ page, request }) => {
  const server = await reading(page, request);
  await option(page, "택시").click();
  await expect(pager(page)).toContainText("2 / 2", { timeout: 3000 });
  await finishReading(server);
  await expect(page.getByText("계획을 다 읽었어요")).toBeVisible({ timeout: 15_000 });
  await expect(pager(page)).toBeVisible();                                                           // 질문을 빼앗지 않는다
  const go = bigButton(page, "읽어 온 계획 확인하기");
  await expect(go).toBeEnabled();
  await expect(page.getByText("남은 질문 1개는 다음에 계획을 읽을 때 다시 답할 수 있어요.")).toBeVisible();
  await page.waitForTimeout(1500);
  await expect(pager(page)).toBeVisible();                                                           // 저절로 넘어가지 않는다
  await go.click();
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible({ timeout: 15_000 });
  await expect(pager(page)).toHaveCount(0);
});

test("읽는 중에 다 답했으면 읽기가 끝난 뒤 3초 막대를 보이고 계획 확인으로 간다. 질문을 만지면 멈추고, 「자동으로 넘어가지 않기」를 누르면 더 이상 저절로 가지 않는다", async ({ page, request }) => {
  const server = await reading(page, request);
  await option(page, "택시").click();
  await expect(pager(page)).toContainText("2 / 2", { timeout: 3000 });
  await option(page, "이동이 편한 곳").click();
  await finishReading(server);
  const line = page.getByText("질문에 모두 답했어요", { exact: true });
  await expect(line).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("3초 뒤에 계획 확인 화면으로 넘어가요.")).toBeVisible();
  // 질문 카드를 만지면 막대가 멈춘다
  await pager(page).getByRole("button", { name: "이전 질문 보기" }).click();
  await expect(line).toHaveCount(0);
  await expect(bigButton(page, "읽어 온 계획 확인하기")).toBeEnabled();
  await page.waitForTimeout(3500);
  await expect(pager(page)).toBeVisible();
  await expect(page.getByText("질문에 모두 답했어요. 아래 단추를 누르면 계획 확인 화면으로 가요.")).toBeVisible();
  await bigButton(page, "읽어 온 계획 확인하기").click();
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible({ timeout: 15_000 });
});

test("「자동으로 넘어가지 않기」를 누르면 다 답했어도 저절로 계획 확인으로 가지 않고 머문다", async ({ page, request }) => {
  const server = await reading(page, request);
  await option(page, "택시").click();
  await expect(pager(page)).toContainText("2 / 2", { timeout: 3000 });
  await option(page, "이동이 편한 곳").click();
  await finishReading(server);
  await expect(page.getByText("질문에 모두 답했어요", { exact: true })).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: "자동으로 넘어가지 않기" }).click();
  await expect(page.getByText("이제 자동으로 넘어가지 않아요.")).toBeVisible();
  await page.waitForTimeout(4000);
  await expect(pager(page)).toBeVisible();
});

test("다 답하고 읽기가 끝나면 3초 막대 뒤에 저절로 계획 확인으로 간다", async ({ page, request }) => {
  const server = await reading(page, request);
  await option(page, "택시").click();
  await expect(pager(page)).toContainText("2 / 2", { timeout: 3000 });
  await option(page, "이동이 편한 곳").click();
  await finishReading(server);
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible({ timeout: 20_000 });
});

test("읽기가 끝난 뒤 30초 아무것도 안 만지면 20초 경고가 뜨고, 「계속 답하기」로 이어가며 몇 번이든 쓸 수 있다. 세는 중에는 숫자가 줄고 0이 되면 계획 확인으로 간다", async ({ page, request }) => {
  test.setTimeout(150_000);
  const server = await reading(page, request);
  await option(page, "택시").click();
  await expect(pager(page)).toContainText("2 / 2", { timeout: 3000 });
  await finishReading(server);
  await expect(bigButton(page, "읽어 온 계획 확인하기")).toBeEnabled({ timeout: 15_000 });
  const warning = page.getByRole("alertdialog");
  await expect(warning).toBeVisible({ timeout: 40_000 });                                              // 30초 + 여유
  await expect(warning).toContainText("아직 보고 계신가요?");
  await expect(warning.getByRole("button", { name: "계속 답하기" })).toBeFocused();
  const first = await warning.locator("p").first().textContent();
  await page.waitForTimeout(3000);
  expect(Number(await warning.locator("p").first().textContent())).toBeLessThan(Number(first));
  await warning.getByRole("button", { name: "계속 답하기" }).click();                                  // 한 번 더
  await expect(warning).toHaveCount(0);
  await expect(pager(page)).toBeVisible();
  await expect(warning).toBeVisible({ timeout: 40_000 });
  await page.keyboard.press("Escape");                                                                 // Esc 도 「계속 답하기」
  await expect(warning).toHaveCount(0);
  await expect(warning).toBeVisible({ timeout: 40_000 });
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible({ timeout: 40_000 });   // 20초가 다 지나면 간다
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
  await expect(page.getByText("기다리는 동안 하나씩 여쭤볼게요.")).toHaveCount(0);
});

test("영어 화면에서는 서버가 보낸 질문 번호로 영어 문구를 쓴다", async ({ page, request }) => {
  await page.addInitScript(() => localStorage.setItem("tripilot.web.settings.v1", JSON.stringify({ language: "en", navigation: "fixed" })));
  const server = mockServer(request);
  await server.scenario({ questions: "two", readingPolls: HOLD });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("Your travel plan").fill(PLAN);
  await page.getByRole("button", { name: "Check my plan" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Turn on and go on" }).click();
  await expect(page.getByRole("region", { name: "2 questions" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "How do you usually get around?" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Public transport" })).toBeVisible();
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
    expect(box!.width).toBeGreaterThanOrEqual(44);
    expect(box!.height).toBeGreaterThanOrEqual(44);
  }
});
