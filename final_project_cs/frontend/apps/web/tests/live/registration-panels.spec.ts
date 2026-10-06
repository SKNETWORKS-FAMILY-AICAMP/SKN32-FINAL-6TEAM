import { expect, test, type Page } from "@playwright/test";
import { checkPlan, fillPlanAsk, finishOnboarding, mockServer, openRegistration, PANES, start, TRIP_ID, weekAhead } from "./helpers";

/**
 * `[2026-10-03 사용자 결정]` 등록 화면의 입력은 세 칸이다 — ①직접 입력 ②파일 선택 ③계획 짜 주기 (테스트).
 * 마지막에 고른 칸만 보내고, 그 칸이 비어 있으면 「계획 확인하기」를 눌러도 넘어가지 않고 이유를 말한다(2026-10-06 부터 단추는 꺼지지 않는다). 테스트용 모방 서버로 도는 자동 시험이다(실제 서버 아님).
 */
const ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const PLAN = "10/1 09:00 경복궁 관람";
const WISH = "조용하고 걷기 좋은 곳 위주로";
const send = (page: Page) => page.getByRole("button", { name: "계획 확인하기" });
const file = (name = "plan.txt") => ({ name, mimeType: "text/plain", buffer: Buffer.from("메모") });
const heading = (page: Page, pane: keyof typeof PANES) => PANES[pane](page).getByRole("heading");

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

test("입력 칸이 셋이고 셋째 칸 제목에 「(테스트)」가 붙으며, 처음에는 직접 입력 칸이 보낼 칸으로 표시된다", async ({ page }) => {
  await start(page);
  await openRegistration(page);
  for (const pane of ["text", "files", "plan"] as const) await expect(PANES[pane](page)).toBeVisible();
  await expect(page.getByRole("heading", { name: "계획 짜 주기 (테스트)", level: 2 })).toBeVisible();
  await expect(PANES.text(page)).toHaveAttribute("aria-current", "true");
  await expect(PANES.text(page).getByText("보낼 칸")).toBeVisible();
  await expect(PANES.files(page)).not.toHaveAttribute("aria-current", "true");
  await expect(PANES.plan(page)).not.toHaveAttribute("aria-current", "true");
  await expect(page.getByText("보낼 칸")).toHaveCount(1);
});

test("칸을 누르거나, 그 안에 쓰거나 고르거나, 키보드 초점이 들어가면 그 칸이 보낼 칸이 된다(한 번에 하나)", async ({ page }) => {
  await start(page);
  await openRegistration(page);
  const active = async () => {
    const names: string[] = [];
    for (const pane of ["text", "files", "plan"] as const) if ((await PANES[pane](page).getAttribute("aria-current")) === "true") names.push(pane);
    return names;
  };
  await heading(page, "files").click();
  expect(await active()).toEqual(["files"]);
  await page.getByLabel("나의 여행 계획").focus();
  expect(await active()).toEqual(["text"]);
  await page.getByLabel("일수", { exact: true }).selectOption("3");
  expect(await active()).toEqual(["plan"]);
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  expect(await active()).toEqual(["text"]);
  await page.locator("#plan-files").focus();                                    // 키보드로 파일 칸에 들어간 것과 같다
  expect(await active()).toEqual(["files"]);
  await page.getByLabel("원하는 여행", { exact: false }).fill(WISH);
  expect(await active()).toEqual(["plan"]);
  await page.getByRole("button", { name: "예시 불러오기" }).click();
  expect(await active()).toEqual(["text"]);
  await page.locator("#plan-files").setInputFiles(file());
  expect(await active()).toEqual(["files"]);
});

for (const theme of ["green", "neutral"] as const) {
  test(`보낼 칸은 글칸에 초점이 있을 때와 같은 강조색 2px 로 둘러진다 — ${theme === "green" ? "초록(기본)" : "흰색"} 테마`, async ({ page }) => {
    await page.addInitScript((value) => localStorage.setItem("tripilot.web.settings.v1", JSON.stringify({ language: "ko", navigation: "fixed", theme: value })), theme);
    await start(page);
    await openRegistration(page);
    expect(await page.evaluate(() => document.documentElement.dataset.theme ?? "green")).toBe(theme);
    // 강조색(--color-primary)이 이 테마에서 실제로 무슨 색인지 — 눈으로 보이는 색으로 바꿔 읽는다
    const primary = await page.evaluate(() => {
      const probe = document.createElement("span");
      probe.style.color = "var(--color-primary)";
      document.body.append(probe);
      const color = getComputedStyle(probe).color;
      probe.remove();
      return color;
    });
    const look = (pane: keyof typeof PANES) => PANES[pane](page).evaluate((element) => {
      const css = getComputedStyle(element);
      return { color: css.borderTopColor, width: css.borderTopWidth, shadow: css.boxShadow };
    });
    const on = await look("text");
    expect(on.color).toBe(primary);
    expect(on.width).toBe("1px");
    expect(on.shadow).toContain(primary);
    expect(on.shadow).toMatch(/0px 0px 0px 1px/);                              // 테두리 1px + 바깥 1px = 2px
    const off = await look("files");
    expect(off.color).not.toBe(primary);
    expect(off.shadow).not.toContain(primary);
    // 강조는 0.15초에 걸쳐 바뀐다 — 다 바뀐 뒤의 색을 본다
    await heading(page, "plan").click();
    await expect.poll(async () => (await look("plan")).color).toBe(primary);
    await expect.poll(async () => (await look("text")).color).not.toBe(primary);
  });
}

test("고른 칸에 값이 없으면 「계획 확인하기」를 눌러도 넘어가지 않고 칸마다 이유를 알리며(단추는 꺼지지 않는다), 값이 있으면 항로 지킴이 카드가 열린다(서버로는 아무것도 가지 않는다)", async ({ page, request }) => {
  // ★2026-10-06 사용자 지시: 단추를 꺼 두지 않는다 — 누르면 입력칸 아래에 이유가 뜨고 그 칸으로 초점이 가며, 쓰기 시작하면 이유가 사라진다.
  const server = mockServer(request);
  await start(page);
  await openRegistration(page);
  const reason = page.locator("#plan-error");
  const card = page.getByRole("dialog");
  await expect(send(page)).not.toHaveAttribute("disabled");
  // ① 글: 비어 있으면 이유 + 초점
  await send(page).click({ force: true });
  await expect(reason).toContainText("여행 계획을 적거나 파일을 올려 주세요.");
  await expect(page.locator("#plan-source")).toBeFocused();
  await expect(page.locator("#plan-source")).toHaveAttribute("aria-invalid", "true");
  await expect(card).toHaveCount(0);
  await page.getByLabel("나의 여행 계획").fill("경복궁");                                                // 쓰기 시작하면 이유가 사라진다
  await expect(reason).toHaveCount(0);
  await page.getByLabel("나의 여행 계획").fill("");
  // ② 파일: 칸을 누르면 그 칸이 고른 칸이 되고, 파일이 없으니 이유
  await heading(page, "files").click();
  await send(page).click({ force: true });
  await expect(reason).toContainText("위에서 고른 「파일 선택」 칸에 파일을 하나 이상 골라 주세요");
  await page.locator("#plan-files").setInputFiles(file());
  await expect(reason).toHaveCount(0);                                                                // 파일을 고르면 이유가 사라진다
  await send(page).click({ force: true });
  await expect(card).toBeVisible();                                                                   // 값이 있으니 카드가 열린다
  await page.keyboard.press("Escape");                                                                // 카드를 닫으면 아무것도 정해지지 않고
  await expect(card).toHaveCount(0);
  await expect(send(page)).toBeFocused();                                                             // 초점이 단추로 돌아온다
  await page.getByRole("button", { name: "plan.txt 빼기" }).click();
  // ③ 계획 짜기: 첫날 · 일수 · 인원을 모두 골라야 한다 (원하는 여행은 비워도 된다)
  await heading(page, "plan").click();
  await send(page).click({ force: true });
  await expect(reason).toContainText("위에서 고른 「계획 짜 주기」 칸에서 첫날 · 일수 · 인원을 모두 골라 주세요");
  await page.getByLabel("첫날", { exact: true }).fill(weekAhead());
  await page.getByLabel("일수", { exact: true }).selectOption("2");
  await send(page).click({ force: true });
  await expect(reason).toContainText("첫날 · 일수 · 인원을 모두 골라 주세요");                           // 인원이 아직이다
  await page.getByLabel("인원", { exact: true }).selectOption("2");
  await send(page).click({ force: true });
  await expect(card).toBeVisible();
  await page.keyboard.press("Escape");
  // 일수 7·인원 4 가 끝이고, 다시 「고르기」로 되돌리면 이유가 다시 나온다
  await page.getByLabel("일수", { exact: true }).selectOption("7");
  await page.getByLabel("인원", { exact: true }).selectOption("4");
  await page.getByLabel("인원", { exact: true }).selectOption("0");
  await send(page).click({ force: true });
  await expect(reason).toContainText("첫날 · 일수 · 인원을 모두 골라 주세요");
  await page.getByLabel("인원", { exact: true }).selectOption("1");
  // 다른 칸에 값이 있어도 고른 칸이 비면 못 넘어간다: 글을 쓰면 글 칸이 고른 칸이 되고, 계획 칸을 다시 누르면 그 칸 기준이다
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await expect(PANES.text(page)).toHaveAttribute("aria-current", "true");
  await page.getByLabel("첫날", { exact: true }).fill("");
  await expect(PANES.plan(page)).toHaveAttribute("aria-current", "true");
  await send(page).click({ force: true });
  await expect(reason).toContainText("첫날 · 일수 · 인원을 모두 골라 주세요");
  await heading(page, "text").click();
  await send(page).click({ force: true });
  await expect(card).toBeVisible();
  expect(await server.received("POST", "/v1/web/trip-intakes")).toHaveLength(0);                      // 카드에서 정하기 전에는 서버로 아무것도 가지 않는다
});

test("첫날은 오늘(서울 날짜)부터 고를 수 있고, 지난 날을 적고 누르면 이유를 말한다", async ({ page }) => {
  const today = new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Seoul" });
  await start(page);
  await openRegistration(page);
  await expect(page.getByLabel("첫날", { exact: true })).toHaveAttribute("min", today);
  await fillPlanAsk(page, { start: "2020-01-01", days: 2, party: 2 });
  await send(page).click({ force: true });
  await expect(page.locator("#plan-error")).toContainText("첫날은 오늘(서울 기준)이거나 그 뒤여야 해요");
  await page.getByLabel("첫날", { exact: true }).fill(today);
  await expect(page.locator("#plan-error")).toHaveCount(0);
  await send(page).click({ force: true });
  await expect(page.getByRole("dialog")).toBeVisible();
});

test("고른 칸만 보낸다 — 글 칸이 고른 칸이면 파일은 가지 않고, 파일 칸이 고른 칸이면 글은 가지 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 0 });
  await start(page);
  await openRegistration(page);
  // 파일을 먼저 골랐다가 글 칸에 쓴다 → 글만 간다
  await page.locator("#plan-files").setInputFiles(file());
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await checkPlan(page);
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);
  let [sent] = await server.received("POST", "/v1/web/trip-intakes");
  expect(String(sent.body?.multipart)).toContain(PLAN);
  expect(String(sent.body?.multipart)).not.toContain('filename="plan.txt"');

  // 글이 남아 있는 채로 파일 칸을 고른다 → 파일만 간다 (쓴 글은 그대로 두고 보내지 않는다)
  await openRegistration(page);
  await expect(page.getByLabel("나의 여행 계획")).toHaveValue(PLAN);
  await page.locator("#plan-files").setInputFiles(file());
  await checkPlan(page);
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);
  [, sent] = await server.received("POST", "/v1/web/trip-intakes");
  expect(String(sent.body?.multipart)).toContain('filename="plan.txt"');
  expect(String(sent.body?.multipart)).not.toContain(PLAN);
  expect(await server.received("POST", "/plan")).toHaveLength(0);
});

test("계획 짜 주기를 보내면 글·파일은 가지 않고, 곧바로 진행 화면에서 「일정을 짜는 중이에요」와 서버의 단계를 보이고, 끝나면 여행 화면으로 간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 0, planDelay: 1500 });
  await start(page);
  await openRegistration(page);
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await page.locator("#plan-files").setInputFiles(file());
  await fillPlanAsk(page, { start: weekAhead(), days: 3, party: 2, wish: WISH });
  await checkPlan(page);

  await expect(page).toHaveURL(/\/intakes\/starting$/);
  await expect(page.getByLabel("나의 여행 계획")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "일정을 짜는 중이에요", level: 1 })).toBeVisible();
  // 읽을 계획 줄이 없는 화면이다 — 「올린 계획」 목록 대신 서버가 말하는 단계가 보인다
  await expect(page.getByText("올린 계획")).toHaveCount(0);
  await expect(page.getByRole("status").filter({ hasText: "여행으로 등록하는 중이에요" })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`), { timeout: 15_000 });

  // 서버가 받은 것: 접수에는 「원하는 여행」 글만(쓴 글과 파일은 없다), 일정 짜기에는 고른 조건과 읽은 일정을 쓰지 않는다는 표시
  const [intake] = await server.received("POST", "/v1/web/trip-intakes");
  const multipart = String(intake.body?.multipart);
  expect(multipart).toContain(WISH);
  expect(multipart).not.toContain(PLAN);
  expect(multipart).not.toContain("filename=");
  const [plan] = await server.received("POST", "/plan");
  expect(plan.accept).toContain("text/event-stream");
  expect(plan.body).toEqual({ revision: 1, start_date: weekAhead(), days: 3, party_size: 2, keep_read_items: false, survey: { version: "2026-09-24.v1", pace: "moderate", on_disruption: "replace" } });   // 설문을 안 마쳤어도 계획 담기에서 정한 것은 간다
  expect(await server.received("POST", "/confirm")).toHaveLength(0);
});

test("원하는 여행을 비워도 보낼 수 있다 — 빈 글로 접수하고 곧바로 일정을 짜게 한다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 0 });
  await start(page);
  await openRegistration(page);
  await fillPlanAsk(page, { start: weekAhead(), days: 1, party: 1 });
  await checkPlan(page);
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`), { timeout: 15_000 });
  const [intake] = await server.received("POST", "/v1/web/trip-intakes");
  expect(String(intake.body?.multipart)).toMatch(new RegExp(String.raw`name="text"\r\n\r\n\r\n--`));
  expect((await server.received("POST", "/plan"))[0].body).toMatchObject({ days: 1, party_size: 1 });
});

test("설문을 마친 사람의 계획 짜 주기에는 설문이 실려 간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 0, trips: "none" });
  await start(page, "acop_u_known");
  await finishOnboarding(page);
  await page.getByRole("button", { name: "여행 계획 등록하기" }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await fillPlanAsk(page, { start: weekAhead(), days: 2, party: 2 });
  await checkPlan(page);
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`), { timeout: 15_000 });
  expect((await server.received("POST", "/plan"))[0].body).toEqual({
    revision: 1, start_date: weekAhead(), days: 2, party_size: 2, keep_read_items: false, survey: { version: "2026-09-24.v1", pace: "relaxed", on_disruption: "replace" } });   // 설문의 여유는 그대로, 항로 지킴이는 「켜고 진행」
});

test("서버가 짜기를 거절하면 등록 화면으로 돌아와 서버의 문장을 보이고, 고른 조건·쓴 글이 그대로 남아 고쳐 다시 보낼 수 있다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 0, planRefusal: "이 조건으로는 일정을 짤 수 없어요 — 일수를 늘려 보세요" });
  await start(page);
  await openRegistration(page);
  await fillPlanAsk(page, { start: weekAhead(), days: 1, party: 3, wish: WISH });
  await checkPlan(page);

  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(page.locator("#plan-error")).toContainText("이 조건으로는 일정을 짤 수 없어요 — 일수를 늘려 보세요");
  await expect(PANES.plan(page)).toHaveAttribute("aria-current", "true");        // 보낸 칸이 다시 고른 칸이다
  await expect(page.getByLabel("첫날", { exact: true })).toHaveValue(weekAhead());
  await expect(page.getByLabel("일수", { exact: true })).toHaveValue("1");
  await expect(page.getByLabel("인원", { exact: true })).toHaveValue("3");
  await expect(page.getByLabel("원하는 여행", { exact: false })).toHaveValue(WISH);
  await expect(send(page)).not.toHaveAttribute("disabled");

  // 조건을 고치면 문장은 사라지고, 서버가 받아 주면 이번엔 여행 화면까지 간다
  await server.scenario({ planRefusal: "" });
  await page.getByLabel("일수", { exact: true }).selectOption("3");
  await expect(page.locator("#plan-error")).toHaveCount(0);
  await checkPlan(page);
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`), { timeout: 15_000 });
  expect(await server.received("POST", "/plan")).toHaveLength(2);
});

test("접수 자체를 서버가 거절해도(계획 짜 주기) 등록 화면으로 돌아와 문장을 보이고 조건이 남는다", async ({ page, request }) => {
  await mockServer(request).scenario({ readingPolls: 0, intakeRefusal: "오늘은 접수를 더 받을 수 없어요" });
  await start(page);
  await openRegistration(page);
  await fillPlanAsk(page, { start: weekAhead(), days: 4, party: 2 });
  await checkPlan(page);
  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(page.locator("#plan-error")).toContainText("오늘은 접수를 더 받을 수 없어요");
  await expect(PANES.plan(page)).toHaveAttribute("aria-current", "true");
  await expect(page.getByLabel("일수", { exact: true })).toHaveValue("4");
});

test("원하는 여행을 서버가 아직 읽는 중이면 다 읽을 때까지 기다린 뒤에 짜 달라고 하고, 기다리는 동안 서버의 읽는 단계를 보인다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 2 });
  await start(page);
  await openRegistration(page);
  await fillPlanAsk(page, { start: weekAhead(), days: 2, party: 2, wish: WISH });
  await checkPlan(page);
  await expect(page).toHaveURL(/\/intakes\/starting$/);
  await expect(page.getByRole("status").filter({ hasText: "계획을 읽는 중이에요" })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`), { timeout: 20_000 });
  const log = await server.log();
  const planAt = log.findIndex((entry) => entry.method === "POST" && entry.path.endsWith("/plan"));
  expect(planAt).toBeGreaterThan(0);
  const readsBefore = log.slice(0, planAt).filter((entry) => entry.method === "GET" && entry.path.endsWith(ID)).length;
  expect(readsBefore).toBeGreaterThanOrEqual(3);                                  // 읽는 중 · 읽는 중 · 읽기 끝 — 그제야 짜 달라고 한다
});

test("서버가 읽는 동안 뒤로 가면 등록 화면으로 돌아가고, 읽기가 끝나도 일정은 짜지 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 2 });
  await start(page);
  await openRegistration(page);
  await fillPlanAsk(page, { start: weekAhead(), days: 2, party: 2, wish: WISH });
  await checkPlan(page);
  await expect(page.getByRole("status").filter({ hasText: "계획을 읽는 중이에요" })).toBeVisible();
  await page.getByRole("button", { name: "뒤로" }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(page.locator("#plan-error")).toHaveCount(0);
  // 돌아와도 고른 칸과 조건·쓴 글이 그대로다
  await expect(PANES.plan(page)).toHaveAttribute("aria-current", "true");
  await expect(page.getByLabel("일수", { exact: true })).toHaveValue("2");
  await expect(page.getByLabel("원하는 여행", { exact: false })).toHaveValue(WISH);
  await page.waitForTimeout(4500);                                                 // 서버의 읽기가 끝날 만큼 기다려도
  await expect(page).toHaveURL(/\/trips\/new$/);
  expect(await server.received("POST", "/plan")).toHaveLength(0);
});

test("영어 화면에서도 칸 제목과 이유 · 읽는 기준 · 항로 지킴이 카드가 영어로 나온다", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("tripilot.web.settings.v1", JSON.stringify({ language: "en", navigation: "fixed" })));
  await start(page);
  await openRegistration(page);
  await expect(page.getByRole("region", { name: "Plan it for me (test)" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Type it in" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Check my plan" })).not.toHaveAttribute("disabled");
  await page.getByRole("button", { name: "Check my plan" }).click({ force: true });
  await expect(page.locator("#plan-error")).toContainText("Write your plan or upload a file.");
  await page.getByLabel("Your travel plan").fill("Gyeongbokgung 10/1 09:00");
  await page.getByRole("button", { name: "Check my plan" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("dialog").getByRole("button", { name: /Turn on/ })).toBeVisible();
});

test("320px 폭에서도 세 칸 · 읽는 기준이 화면을 넘지 않고, 눌렀을 때 이유가 보인다", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 720 });
  await start(page);
  await openRegistration(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await send(page).click({ force: true });
  await expect(page.locator("#plan-error")).toBeVisible();
  await heading(page, "plan").click();
  await page.getByLabel("첫날", { exact: true }).scrollIntoViewIfNeeded();
  for (const label of ["첫날", "일수", "인원"]) {
    const box = await page.getByLabel(label, { exact: true }).boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(320);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("빈 채로 「계획 확인하기」를 누르면 칸 맨 아래가 아니라 고른 입력칸 바로 아래에 눈에 띄는 안내가 뜨고(화면이 그 자리로 옮겨 간다), 서버로는 아무것도 가지 않으며, 예시 글은 예시라고 적혀 있다", async ({ page, request }) => {
  const server = mockServer(request);
  await page.setViewportSize({ width: 1280, height: 640 });                                            // 낮은 화면: 입력칸 아래 안내가 가려지기 쉬운 크기
  await start(page);
  await openRegistration(page);
  await expect(page.getByLabel("나의 여행 계획")).toHaveAttribute("placeholder", /^예시 — 이런 식으로 적어 주세요/);
  const notice = page.locator("#plan-error");
  // ① 글: 공백뿐이어도 빈 것이다
  await page.getByLabel("나의 여행 계획").fill("   \n  ");
  await send(page).click({ force: true });
  await expect(PANES.text(page).locator("#plan-error")).toContainText("여행 계획을 적거나 파일을 올려 주세요.");
  await expect(notice).toBeInViewport();
  const box = (await notice.boundingBox())!;
  const field = (await page.getByLabel("나의 여행 계획").boundingBox())!;
  expect(box.y).toBeGreaterThanOrEqual(field.y + field.height - 40);                                   // 입력칸 바로 아래(칸 안쪽 아래 줄 다음)
  expect(box.y - (field.y + field.height)).toBeLessThan(120);
  expect(await notice.evaluate((element) => getComputedStyle(element).fontSize)).toBe("14px");        // 작은 글씨가 아니다
  // ② 파일 칸을 골랐을 때는 그 칸 안에 뜬다
  await heading(page, "files").click();
  await send(page).click({ force: true });
  await expect(PANES.files(page).locator("#plan-error")).toContainText("파일을 하나 이상 골라 주세요");
  await expect(page.locator("#plan-error")).toHaveCount(1);                                            // 어디에나 하나뿐이다
  // ③ 계획 짜 주기 칸
  await heading(page, "plan").click();
  await send(page).click({ force: true });
  await expect(PANES.plan(page).locator("#plan-error")).toContainText("첫날 · 일수 · 인원을 모두 골라 주세요");
  await expect(notice).toBeInViewport();
  expect(await server.received("POST", "/v1/web/trip-intakes")).toHaveLength(0);
  await expect(page).toHaveURL(/\/trips\/new$/);
});
