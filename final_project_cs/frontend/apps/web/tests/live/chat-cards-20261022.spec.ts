import { expect, test, type Page } from "@playwright/test";
import { mockServer, openPane, start, TRIP_ID, tripScreen } from "./helpers";

/**
 * `[2026-10-22 사용자 결정 — ST4F-719 · 목업 guguroute-chat-ui-2026-10-22.html ② + ⓑ]` The chat pane: chips that follow the situation in one sliding row, answers as cards, the server's choices
 * under the answer, and one short line under the field with 「자세히」. The mock server's trip runs 2026-10-01 → 10-02; the page's clock runs from the morning of day 1, so the trip opens on day 1.
 * The answers are the server's own frames (`trip_facts.py` · `chat_edit.py`, 2026-10-22) sent by `page.route` — the mock server's chat answers only 「서버 답: …」.
 */
const log = (page: Page) => page.getByRole("log", { name: "여행 대화 이력" });
const chips = (page: Page) => page.getByRole("group", { name: "빠른 질문" });
const answers = (page: Page) => log(page).locator("[data-chat-answer]");
const sent: Record<string, unknown>[] = [];

async function answerWith(page: Page, ...bodies: Record<string, unknown>[]) {
  await page.route((url) => url.pathname.endsWith(`/trips/${TRIP_ID}/messages`), async (route) => {
    sent.push(route.request().postDataJSON());
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(bodies[Math.min(sent.length, bodies.length) - 1]) });
  });
}

test.beforeEach(async ({ page, request }) => {
  sent.length = 0;
  await mockServer(request).reset();
  await start(page);
  await page.clock.install({ time: new Date("2026-10-01T06:00:00+09:00") });
  await page.clock.resume();
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(tripScreen(page)).toBeVisible();
});

test("고른 일정이 있으면 칩 줄 머리가 「○○에 대해」, 줄은 옆으로 밀리고 채팅 칸 밀기와 구분된다 — 「선택 일정」 답에는 장소 카드, 「상세 보기」 뒤 ← 로 채팅 칸에 돌아온다", async ({ page }) => {
  await answerWith(page, { status: "answered", case_status: "resolved", answer: "경복궁 관람 일정이에요 — 10월 1일(목) 09:30~11:00 · 활동\n· 그날 영업: 09:00~18:00" });
  await page.locator("#stop-button-i-b").click();
  await openPane(page, "채팅");
  await expect(page.locator("[data-chat-chips]")).toContainText("경복궁 관람에 대해");
  await expect(chips(page)).toHaveAttribute("data-no-swipe");
  await expect(chips(page).getByRole("button", { name: "가는 길", exact: true })).toBeVisible();
  await chips(page).getByRole("button", { name: "선택 일정", exact: true }).click();
  const card = answers(page).last();
  await expect(card).toContainText("답변");
  await expect(card.locator('[data-place-card="i-b"]')).toContainText("경복궁");
  expect(sent[0]).toMatchObject({ item_id: "i-b" });
  await card.getByRole("button", { name: "경복궁 관람 상세 보기", exact: true }).click();
  await expect(page.getByRole("button", { name: "상세 보기 닫기" })).toBeVisible();
  await page.getByRole("button", { name: "상세 보기 닫기" }).click();
  await expect(page.locator("#trip-pane-chat")).not.toHaveAttribute("inert");
  await expect(card).toBeVisible();
});

test("하루 요약 답은 타임라인 카드로 — 카드와 글자까지 같은 서버 일정 줄은 빠지고, 머리 줄 · 이동 줄 · 값이 다른 줄은 남는다", async ({ page }) => {
  await answerWith(page, { status: "answered", case_status: "resolved", answer: ["10월 1일(목) 일정은 3곳이에요.", "· 08:00~09:00 아침 식당(식사)", "   ↳ 이동: 09:00 출발 · 도보 · 약 10분",
    "· 09:30~11:00 경복궁 관람(활동)", "· 12:00~13:30 점심 식당(식사)"].join("\n") });
  await openPane(page, "채팅");
  await expect(page.locator("[data-chat-chips]")).toContainText("1일차 · 지금 06:0");
  await chips(page).getByRole("button", { name: "하루 요약", exact: true }).click();
  const card = answers(page).last();
  await expect(card.locator("ol")).toContainText("아침 식당");
  const body = card.locator("p").first();
  await expect(body).toContainText("10월 1일(목) 일정은 3곳이에요.");
  await expect(body).toContainText("↳ 이동: 09:00 출발 · 도보 · 약 10분");
  await expect(body).toContainText("· 12:00~13:30 점심 식당(식사)");          // 13:30 ≠ the plan's 13:00 — left in
  await expect(body).not.toContainText("· 08:00~09:00 아침 식당(식사)");
  await expect(body).not.toContainText("· 09:30~11:00 경복궁 관람(활동)");
  expect(sent[0]).toMatchObject({ summary_day: "2026-10-01" });
});

test("서버 선택지는 칩 줄이 아니라 답 카드 아래에 줄을 바꿔 전부 — 분을 묻는 되묻기엔 화면이 만든 빠른 답 칩이 칩 줄에 뜨고, 한 번 쓰면 사라진다", async ({ page }) => {
  const long = "1일차 09:30 경복궁 관람 몇 시에 가는지 알려 줘";
  await answerWith(page,
    { status: "answered", case_status: "resolved", answer: "경복궁 운영시간을 알려 드렸어요.", choices_title: "혹시 이런 뜻이었나요?", choices: [{ label: long, message: long }] },
    { status: "clarify", case_status: "waiting_input", case_id: "c-wait", required_input_schema: { type: "object", required: ["minutes"] }, answer: "몇 분쯤 늦으세요? 예를 들어 ‘30분이요’라고 알려 주세요." },
    { status: "still_fits", case_status: "resolved", case_id: "c-wait", answer: "지금 일정 그대로도 괜찮아요 — 바꾸지 않았어요." });
  await openPane(page, "채팅");
  await page.locator("#trip-chat-message").fill("경복궁 몇 시까지 해?");
  await page.locator("#trip-chat-message").press("Enter");
  await expect(answers(page).last().getByRole("button", { name: long, exact: true })).toBeVisible();
  await expect(chips(page).getByRole("button", { name: long, exact: true })).toHaveCount(0);
  await page.locator("#trip-chat-message").fill("좀 늦을 것 같아");
  await page.locator("#trip-chat-message").press("Enter");
  await expect(answers(page).last()).toContainText("답을 기다려요");
  await expect(page.locator("[data-chat-chips]")).toContainText("답하기");
  await expect(chips(page).getByRole("button", { name: "15분이요", exact: true })).toHaveAttribute("data-made");
  await chips(page).getByRole("button", { name: "30분이요", exact: true }).click();
  await expect(answers(page).last()).toContainText("바꾸지 않았어요");
  expect(sent[2]).toMatchObject({ message: "30분이요", case_id: "c-wait" });
  await expect(chips(page).getByRole("button", { name: "15분이요", exact: true })).toHaveCount(0);
});

test("입력창 아래 짧은 안내 + 「자세히」 — 펼친 전체 문장은 창 밖을 누르거나 Esc 로 닫히고, 채팅 칸은 그대로다", async ({ page }) => {
  await openPane(page, "채팅");
  const more = page.getByRole("button", { name: "자세히", exact: true });
  await expect(page.locator("#trip-chat-note")).toHaveText("숙소 · 항공 · 예약한 일정은 「일정 수정」에서 바꿔요");
  await expect(page.locator("#trip-chat-message")).toHaveAttribute("aria-describedby", /trip-chat-note/);
  await more.click();
  const full = page.getByRole("note");
  await expect(full).toContainText("채팅으로 일정을 바꾸면 여행계획서에 새 판이 생겨요.");
  await log(page).click({ position: { x: 20, y: 20 } });
  await expect(full).toHaveCount(0);
  await more.click();
  await expect(full).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(full).toHaveCount(0);
  await expect(page.locator("#trip-pane-chat")).not.toHaveAttribute("inert");
  await more.click();
  await more.click();
  await expect(full).toHaveCount(0);
});
