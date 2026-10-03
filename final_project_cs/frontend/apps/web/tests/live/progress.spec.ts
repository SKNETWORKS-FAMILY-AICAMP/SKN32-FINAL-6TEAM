import { expect, test, type Page } from "@playwright/test";
import { fillPlanAsk, openRegistration, start, mockServer, TRIP_ID, weekAhead } from "./helpers";

// `[2026-10-02]` The server answers long work as a progress stream (`op_stream.py`): chat and 「plan it for me」 when
// asked with `Accept: text/event-stream`, and an intake's reading on `GET …/events`. The screen shows what the server
// says it is doing, reconnects a silent line with the same request, and reads the server's errors.

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const openChat = async (page: Page) => {
  await start(page);
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(page.getByRole("heading", { name: "나의 여행", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "채팅", exact: true }).click();
  return page.locator("#trip-pane-chat");
};

test("채팅: 스트림으로 물어 서버가 말하는 단계와 「느려요」를 보이고, 끝나면 답을 보인다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ stream: "slow" });
  const chat = await openChat(page);
  await chat.getByRole("button", { name: "하루 요약" }).click();
  const waiting = chat.getByRole("status").filter({ hasText: /중이에요/ });
  await expect(waiting).toContainText("요청을 이해하는 중이에요");
  await expect(waiting).toContainText("응답이 느려요 (12초째)");
  await expect(chat.locator("article[data-role=assistant]").last()).toContainText("서버 답: 2026-10-01 하루 일정을 요약해 주세요.");
  const [sent] = await server.received("POST", "/messages");
  expect(sent.accept).toContain("text/event-stream");
});

test("채팅: 스트림이 조용해지면(박동 두 번) 「다시 연결」을 알리고 같은 요청 번호로 다시 보내 답을 받는다", async ({ page, request }) => {
  test.setTimeout(45_000);
  const server = mockServer(request);
  await server.scenario({ stream: "drop" });
  const chat = await openChat(page);
  await chat.getByRole("button", { name: "하루 요약" }).click();
  await expect(chat.getByRole("status").filter({ hasText: "서버와 연결이 끊겼어요 — 다시 연결하는 중이에요" })).toBeVisible({ timeout: 15_000 });
  await expect(chat.locator("article[data-role=assistant]").last()).toContainText("서버 답: 2026-10-01 하루 일정을 요약해 주세요.", { timeout: 15_000 });
  const ids = (await server.received("POST", "/messages")).map((entry) => entry.body?.request_id);
  expect(ids).toHaveLength(2);
  expect(ids[1]).toBe(ids[0]);
});

test("채팅: 서버의 오류 이벤트는 그 문장으로 보이고, 「다시 보내기」는 같은 요청 번호로 간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ stream: "error" });
  const chat = await openChat(page);
  await chat.getByRole("button", { name: "하루 요약" }).click();
  const failed = chat.getByRole("alert").filter({ hasText: "메시지를 보내지 못했어요" });
  await expect(failed).toContainText("시간이 오래 걸려 기다리기를 멈췄어요");
  await server.scenario({ stream: "on" });
  await failed.getByRole("button", { name: "다시 보내기" }).click();
  await expect(chat.locator("article[data-role=assistant]").last()).toContainText("서버 답: 2026-10-01 하루 일정을 요약해 주세요.");
  const ids = (await server.received("POST", "/messages")).map((entry) => entry.body?.request_id);
  expect(ids).toEqual([ids[0], ids[0]]);
});

test("채팅: 열린 실시간 연결이 상한이면(429) 서버 문장을 보이고, 스트림이 없는 옛 서버는 전처럼 JSON 답을 보인다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ stream: "busy" });
  const chat = await openChat(page);
  await chat.getByRole("button", { name: "하루 요약" }).click();
  await expect(chat.getByRole("alert").filter({ hasText: "메시지를 보내지 못했어요" })).toContainText("열어 둔 실시간 연결이 너무 많다");
  await server.scenario({ stream: "off" });
  await chat.getByRole("alert").getByRole("button", { name: "다시 보내기" }).click();
  await expect(chat.locator("article[data-role=assistant]").last()).toContainText("서버 답: 2026-10-01 하루 일정을 요약해 주세요.");
});

test("계획 짜 주기: 진행 화면이 「일정을 짜는 중이에요」와 서버가 말하는 단계(짜기 → 조건 확인 → 등록)를 보이고, 끝나면 여행 화면으로 간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 0, planDelay: 1500 });
  await start(page);
  await openRegistration(page);
  await fillPlanAsk(page, { start: weekAhead(), days: 2, party: 2 });
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page).toHaveURL(/\/intakes\/starting$/);
  await expect(page.getByRole("heading", { name: "일정을 짜는 중이에요", level: 1 })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "여행으로 등록하는 중이에요" })).toBeVisible();
  // 서버가 말한 단계가 막대에 그대로 서 있다: 앞의 두 점은 지났고 마지막(등록)이 지금이다
  await expect(page.getByRole("progressbar", { name: "일정 짜기 진행" })).toHaveAttribute("aria-valuetext", /여행 등록/);
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`), { timeout: 15_000 });
  const [plan] = await server.received("POST", "/plan");
  expect(plan.accept).toContain("text/event-stream");
});

const upload = async (page: Page) => {
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill("10/1 09:00 경복궁 관람");
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);
};

test("접수 읽기: 서버의 진행 스트림을 따라 다시 읽고(1.5초 조회 없음), 읽기가 끝나면 확인 화면으로 넘어간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 3 });
  await upload(page);
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible();
  const streams = await server.received("GET", "/events");
  expect(streams.length).toBeGreaterThan(0);
  expect(streams[0].accept).toContain("text/event-stream");
});

test("접수 읽기: 서버의 진행 알림(progress)이 오면 머리글 막대에 「3/14 · 광장시장 이동 확인 중」처럼 서버가 말한 대로 보인다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 3, board: "rich", review: "on" });             // the server's own check on (it streams what it checked and how far); three stops and two legs: the check stays on screen long enough to read
  await upload(page);
  // the stub ends with the leg phase: "<done>/<total> · <name of the stop it leads to> 이동 확인 중"
  await expect(page.getByRole("progressbar", { name: "계획 확인 진행" })).toContainText(/\d+\/\d+ · .+ 이동 확인 중/);
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible();
});

test("접수 읽기: 진행 알림을 안 보내는 서버면 막대는 지금처럼 움직이고 「x/y」 줄은 말하지 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 3, intakeProgress: "off" });
  await upload(page);
  const bar = page.getByRole("progressbar", { name: "계획 확인 진행" });
  await expect(bar).toBeVisible();
  await expect(bar).not.toContainText(/\d+\/\d+ · /);
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible();
});

test("접수 읽기: 스트림이 없는 옛 서버(404)면 전처럼 1.5초마다 다시 읽어 확인 화면으로 넘어간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 3, intakeEvents: "off" });
  await upload(page);
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible({ timeout: 15_000 });
  expect((await server.received("GET", "/v1/web/trip-intakes/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")).length).toBeGreaterThanOrEqual(4);
});

test("접수 읽기: 서버가 읽기가 멈췄다고(stalled) 하면 「읽는 중」에 두지 않고 다시 올리기를 권한다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 99, intakeEvents: "stalled" });
  await upload(page);
  await expect(page.getByRole("heading", { name: "서버가 이 계획을 끝까지 읽지 못했어요" })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "읽던 서버가 다시 시작됐을 수 있어요" })).toContainText("계획을 다시 올려 주세요");
  await page.getByRole("link", { name: "다시 올리기" }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
});
