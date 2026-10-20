import { expect, test, type Page } from "@playwright/test";
import { agree, checkPlan, mockServer, start } from "./helpers";
import { needsBadge } from "./plan-check-kit";

/**
 * `[2026-10-20 사용자 결정 — ST4F-615]` 「직접 입력」은 「계획 확인하기」를 눌러도 화면을 넘기지 않는다 — 입력칸을 잠그고 「보내는 중」을 보이며 접수 응답(서버의 빠른 거름)을
 * 그 화면에서 기다린다. 걸렸으면(`screened`) 그대로 머물러 「일정을 찾지 못했어요 …」와 함께 입력칸에 초점을 주고, 서버가 받으면 (항로 지킴이 카드 뒤) 그 접수의 진행 화면으로 넘어간다.
 * `[2026-10-03 사용자 지시]` 파일 칸 · 「계획 짜 주기」는 지금처럼 누르면 곧바로 진행 화면(`/intakes/starting`)으로 넘어간다.
 * 테스트용 모방 서버로 도는 자동 시험(실제 서버 아님).
 */
const PLAN = "10/1 09:00 경복궁 관람\n12:00 광장시장 점심";
const LOADING = "여행 정보를 불러오고 있어요";
const SENDING = "계획을 서버로 보내는 중이에요…";
const NOT_FOUND = "일정을 찾지 못했어요";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

/** 일반 불러오기 화면이 한 순간이라도 뜨면 기록해 둔다(마지막에 한 번 본다). 등록 화면이 처음 열릴 때 자기 글을 읽는 순간은 세지 않도록 누르기 직전에 `forgetLoadingScreen` 으로 지운다. */
async function watchForLoadingScreen(page: Page) {
  await page.addInitScript((phrase) => {
    (window as unknown as { __sawLoading: boolean }).__sawLoading = false;
    new MutationObserver(() => {
      if (document.body?.innerText.includes(phrase)) (window as unknown as { __sawLoading: boolean }).__sawLoading = true;
    }).observe(document, { childList: true, subtree: true, characterData: true });
  }, LOADING);
}
const sawLoadingScreen = (page: Page) => page.evaluate(() => (window as unknown as { __sawLoading: boolean }).__sawLoading);
const forgetLoadingScreen = (page: Page) => page.evaluate(() => { (window as unknown as { __sawLoading: boolean }).__sawLoading = false; });
/** 오류 문장 자리(`role=alert`) — 화면 이동을 알리는 Next 의 빈 알림은 세지 않는다. */
const planError = (page: Page) => page.locator("#plan-error");
const box = (page: Page) => page.getByLabel("나의 여행 계획");
const sendButton = (page: Page) => page.getByRole("button", { name: /계획 확인하기|확인을 시작하는 중/ });
const sendingNote = (page: Page) => page.getByRole("status").filter({ hasText: /계획을 서버로 보내는 중이에요|서버가 답하는 데 시간이 걸리고 있어요/ });

/** 「직접 입력」에 쓰고 누른다 — 카드는 여기서 다루지 않는다(서버가 받은 뒤에 뜬다). */
async function writeAndPress(page: Page, text = PLAN) {
  await page.goto("/trips/new");
  await box(page).fill(text);
  await expect(box(page)).toHaveValue(text);
  await forgetLoadingScreen(page);
  await page.getByRole("button", { name: "계획 확인하기" }).click();
}

/** 서버가 받은 뒤에 뜨는 항로 지킴이 카드에서 켜고 진행한다. */
async function turnOnAndGo(page: Page) {
  const card = page.getByRole("dialog");
  await expect(card).toBeVisible({ timeout: 15_000 });
  await card.getByRole("button", { name: "켜고 진행" }).click();
}

test("「직접 입력」: 누르면 입력 화면에 머문 채 입력칸을 잠그고 「보내는 중」을 보이다가, 서버가 받으면 항로 지킴이 카드 뒤 그 접수의 진행 화면으로 넘어가 실시간 진행으로 결과가 나온다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ intakeDelay: 2500, review: "on", board: "rich", intakeEvents: "on", readingPolls: 1 });
  await start(page);
  await watchForLoadingScreen(page);
  await writeAndPress(page);

  // 서버는 아직 답하지 않았다(2.5초): 화면은 그대로이고 입력칸은 잠겨 있으며 「보내는 중」이 보인다. 카드 · 진행 화면은 아직 없다
  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(box(page)).toBeDisabled();
  await expect(sendingNote(page)).toContainText(SENDING);
  await expect(sendButton(page)).toHaveAttribute("aria-busy", "true");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(await server.received("GET", "/events")).toHaveLength(0);

  // 서버가 받으면(빠른 거름 통과) 카드가 묻고, 진행 화면(`/intakes/starting` 을 거치지 않고 그 접수의 화면)으로 넘어가 서버의 진행 알림으로 이어진다
  await turnOnAndGo(page);
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]{36}$/, { timeout: 15_000 });
  await expect(needsBadge(page)).toBeVisible({ timeout: 40_000 });
  expect((await server.received("GET", "/events")).length).toBeGreaterThan(0);
  expect((await server.received("POST", "/v1/web/trip-intakes")).length).toBe(1);
  expect(await sawLoadingScreen(page)).toBe(false);                             // 「여행 정보를 불러오고 있어요」 화면은 한 번도 뜨지 않았다
});

test("「직접 입력」: 빠른 거름에 걸리면(여행 단서가 없는 글) 화면을 넘기지 않고 「일정을 찾지 못했어요 …」를 보이며 입력칸에 초점을 준다 — 글은 그대로, 카드도 진행 화면도 없다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ screen: "off_topic", intakeDelay: 800, readingPolls: 0 });
  await start(page);
  await writeAndPress(page, "파이썬 for 루프에 대해서 알려줘");
  await expect(box(page)).toBeDisabled();                                       // 기다리는 동안은 잠겨 있다
  await expect(planError(page)).toContainText(NOT_FOUND);
  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(box(page)).toBeEnabled();
  await expect(box(page)).toBeFocused();
  await expect(box(page)).toHaveValue("파이썬 for 루프에 대해서 알려줘");
  await expect(sendingNote(page)).toHaveCount(0);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(await server.received("POST", "/v1/web/trip-intakes")).toHaveLength(1);

  // 고쳐 쓰면 문장이 사라지고, 서버가 받아 주면 카드 뒤 진행 화면으로 간다
  await server.scenario({ screen: "pass", intakeDelay: 0 });
  await box(page).fill("10/1 09:00 경복궁 관람");
  await expect(planError(page)).toHaveCount(0);
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await turnOnAndGo(page);
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]{36}$/, { timeout: 15_000 });
  expect(await server.received("POST", "/v1/web/trip-intakes")).toHaveLength(2);
});

test("「직접 입력」을 서버가 거절하면 화면을 넘기지 않고 그 자리에서 서버의 문장을 보이며, 입력칸이 다시 열리고 글은 그대로다", async ({ page, request }) => {
  await mockServer(request).scenario({ intakeRefusal: "계획 글이 너무 길어요 — 12,000자까지 읽어요", readingPolls: 0 });
  await start(page);
  await writeAndPress(page);
  await expect(planError(page)).toContainText("계획 글이 너무 길어요");
  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(box(page)).toBeEnabled();
  await expect(box(page)).toHaveValue(PLAN);
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("파일 칸: 서버가 계획을 거절하면 등록 화면으로 돌아와 서버의 문장을 보이고, 올리려던 파일이 그대로 있어 다시 보낼 수 있다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ intakeRefusal: "계획 글이 너무 길어요 — 12,000자까지 읽어요", readingPolls: 0 });
  await start(page);
  await page.goto("/trips/new");
  await page.locator("#plan-files").setInputFiles({ name: "plan.txt", mimeType: "text/plain", buffer: Buffer.from("메모") });
  await checkPlan(page);

  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(planError(page)).toContainText("계획 글이 너무 길어요");
  await expect(page.getByRole("list", { name: "선택한 파일" })).toContainText("plan.txt");

  // 서버가 받아 주면 진행 화면을 거쳐 접수 화면으로 간다
  await server.scenario({ intakeRefusal: "" });
  await checkPlan(page);
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]{36}$/, { timeout: 15_000 });
  expect((await server.received("POST", "/v1/web/trip-intakes")).length).toBe(2);
});

test("파일 칸: 보내는 중에 뒤로 가기 화살표를 누르면 등록 화면으로 돌아가 파일이 그대로 있고, 오류 문장은 뜨지 않는다", async ({ page, request }) => {
  await mockServer(request).scenario({ intakeDelay: 4000, readingPolls: 0 });
  await start(page);
  await page.goto("/trips/new");
  await page.locator("#plan-files").setInputFiles({ name: "plan.txt", mimeType: "text/plain", buffer: Buffer.from("메모") });
  await checkPlan(page);
  await expect(page).toHaveURL(/\/intakes\/starting$/);
  await page.getByRole("button", { name: "뒤로" }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(page.getByRole("list", { name: "선택한 파일" })).toContainText("plan.txt");
  await expect(planError(page)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "계획 확인하기" })).toBeEnabled();
  // 서버가 늦게 답해도 화면은 끌려가지 않는다
  await page.waitForTimeout(4500);
  await expect(page).toHaveURL(/\/trips\/new$/);
});

test("「직접 입력」: 기다리는 동안 「이전」으로 떠나면, 서버가 늦게 답해도 화면이 끌려가지 않는다", async ({ page, request }) => {
  await mockServer(request).scenario({ intakeDelay: 4000, readingPolls: 0 });
  await start(page);
  await writeAndPress(page);
  await expect(sendingNote(page)).toBeVisible();
  await page.getByRole("button", { name: "이전" }).click();
  await expect(page).not.toHaveURL(/\/trips\/new$/);
  await page.waitForTimeout(4500);
  await expect(page).not.toHaveURL(/\/intakes\//);
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("「직접 입력」: 기다리는 동안 새로고침하면 등록 화면 그대로이고 쓴 글도 그대로다 — 늦은 답이 화면을 끌고 가지 않는다", async ({ page, request }) => {
  await mockServer(request).scenario({ intakeDelay: 4000, readingPolls: 0 });
  await start(page);
  await writeAndPress(page);
  await expect(page).toHaveURL(/\/trips\/new$/);
  await page.reload();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(box(page)).toHaveValue(PLAN);
  await expect(box(page)).toBeEnabled();
  await page.waitForTimeout(4500);
  await expect(page).toHaveURL(/\/trips\/new$/);
});

test("세션이 없는 첫 방문도 입력 화면에서 기다리는 사이 게스트 세션이 만들어지고, 서버가 받으면 진행 화면으로 넘어간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ intakeDelay: 1500, review: "on", board: "rich", readingPolls: 1 });
  await start(page, null);
  await agree(page);                                                                     // 세션은 없지만 약관에는 이미 동의했다(이 시험의 주제는 세션이 만들어지는 때)
  await writeAndPress(page);
  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(sendingNote(page)).toContainText(SENDING);
  await turnOnAndGo(page);
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]{36}$/, { timeout: 15_000 });
  await expect(needsBadge(page)).toBeVisible({ timeout: 40_000 });
  expect((await server.received("POST", "/v1/web/auth/session")).length).toBe(1);
  // 키 안내는 어디에도 없다
  await expect(page.getByText("내 여행 열쇠를 따로 보관해 주세요")).toHaveCount(0);
});

test("서버가 몇 초 넘게 답이 없으면 입력 화면의 「보내는 중」이 「서버가 답하는 데 시간이 걸리고 있어요」로 바뀌고, 답이 오면 그대로 이어진다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ intakeDelay: 6500, review: "on", board: "rich", readingPolls: 1 });
  await start(page);
  await writeAndPress(page);
  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(sendingNote(page)).toContainText(SENDING);
  await expect(sendingNote(page)).toContainText("서버가 답하는 데 시간이 걸리고 있어요", { timeout: 8_000 });     // 4초쯤 뒤
  await turnOnAndGo(page);
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]{36}$/, { timeout: 15_000 });
  await expect(needsBadge(page)).toBeVisible({ timeout: 40_000 });
});

test("파일 칸: 그리기 신호가 오지 않는 화면(숨은 브라우저 창 · 뒤쪽 탭)에서도 계획이 나가고 접수 화면으로 넘어간다 — 옛: 「보내는 중」에서 요청 없이 멈춤 (ST4F-596)", async ({ page, request }) => {
  const server = mockServer(request);
  await page.addInitScript(() => localStorage.setItem("triPilot.guardianDefault.v1", "on"));       // 항로 지킴이를 켜 둔 고객 — 카드 없이 바로 보낸다
  await start(page);
  await page.goto("/trips/new");
  await page.locator("#plan-files").setInputFiles({ name: "plan.txt", mimeType: "text/plain", buffer: Buffer.from("10/1 09:00 경복궁 관람") });
  // 숨은 창처럼 requestAnimationFrame 이 아예 오지 않는다(화면 상태는 「보임」 그대로 — 2026-10-17 앱 브라우저 창을 숨긴 채 재현: 28초 동안 요청 0)
  await page.evaluate(() => { window.requestAnimationFrame = () => 0; });
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page).toHaveURL(/\/intakes\/(?!starting)[^/]+$/);
  expect(await server.received("POST", "/trip-intakes")).toHaveLength(1);                        // 그리기 신호 대신 타이머로 한 번
});
