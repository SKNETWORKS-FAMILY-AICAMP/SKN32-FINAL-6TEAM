import { expect, test } from "@playwright/test";
import { agree, fillPlanAsk, finishOnboarding, openRegistration, start, mockServer, TRIP_ID, weekAhead, checkPlan, tripScreen } from "./helpers";
import { needsBadge } from "./plan-check-kit";

const PLAN = "10/1 09:00 경복궁 관람";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

test("첫 방문: 계획을 올리면 게스트 세션이 만들어지고(쿠키 · 토큰 안내는 없음), 읽은 결과를 확인해 등록하면 여행 화면으로 간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ trips: "none" });
  await start(page, null);
  await agree(page);                                                                     // 이 시험의 주제는 첫 등록이다 - 약관에는 이미 동의한 사람

  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await checkPlan(page);
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);

  // 읽는 중 → 결과 화면. 서버가 읽은 항목과 서버가 찾은 장소가 그대로 보인다.
  const card = page.getByRole("article", { name: "경복궁 관람" });
  await expect(card).toBeVisible();
  await card.getByRole("heading").getByRole("button").click();
  await expect(card.getByText("경복궁", { exact: true })).toBeVisible();

  // 세션이 방금 만들어졌다. `[2026-10-04 사용자 결정]` 키를 보관하라는 안내는 어디에도 없다.
  await expect(page.getByText("내 여행 열쇠를 따로 보관해 주세요")).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible();
  await expect(page.getByText("내 여행 열쇠를 따로 보관해 주세요")).toHaveCount(0);

  await page.getByRole("button", { name: "여행 등록" }).click();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));
  await expect(tripScreen(page)).toBeVisible();

  // 서버가 실제로 받은 것: 계획 글은 접수 때, 확인은 등록할 때. 취향 설문을 안 마쳤어도 계획 담기 화면에서 정한 것(여유 「적당히」 · 항로 지킴이 「켜고 진행」)은 간다.
  const [intake] = await server.received("POST", "/v1/web/trip-intakes");
  expect(String(intake.body?.multipart)).toContain(PLAN);
  const [confirm] = await server.received("POST", "/confirm");
  expect(confirm.body).toEqual({ revision: 1, survey: { version: "2026-09-24.v1", pace: "moderate", on_disruption: "replace" } });
  // ★세션 쿠키와 보안 토큰으로 갔다 — 키 헤더는 없다.
  expect(confirm.session).toBe("stub-session-1");
  expect(confirm.csrf).toBe("csrf-stub-session-1");
  expect(confirm.key).toBeNull();
  expect(await server.received("POST", "/v1/web/auth/session")).toHaveLength(1);       // 게스트 세션은 한 번만 만들어졌다

  // 마이페이지: 게스트라고 말하고, 키는 보여 주지도 받지도 않는다.
  await page.goto("/mypage");
  await expect(page.getByRole("group", { name: "로그인 상태" })).toContainText("게스트로 쓰고 있어요");
  await expect(page.getByText("내 여행 열쇠를 따로 보관해 주세요")).toHaveCount(0);
  await expect(page.getByText("발급된 토큰")).toHaveCount(0);
});

test("서버가 읽는 동안 새 계획 확인 화면이 읽는 중(막대 · 찾은 일정)으로 보이고, 읽기가 끝나면 확인 화면으로 넘어간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 3 });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await checkPlan(page);
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);

  // Reading: the server's own line, not yet read; the bar and the back arrow of the new screen.
  await expect(page.getByRole("heading", { name: "계획을 확인하고 있어요", level: 1 })).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "계획 확인 진행" })).toBeVisible();
  // `[2026-10-07 사용자 지시]` 줄별 목록(「올린 계획」)은 없다 — 막대와 「찾은 일정 n개」만 있다
  await expect(page.getByText("찾은 일정")).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "10/1 09:00 경복궁 관람" })).toHaveCount(0);

  // Reading ends: the screen draws the line as read, holds a moment, then the review takes over. (What a read line
  // shows is held by the unit test of `readingOf`; the moment itself is too short to assert here.)
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "계획을 확인하고 있어요" })).toHaveCount(0);
});

test("온보딩 설문을 마친 뒤 등록하면 설문이 확인 요청에 실려 가고, 계획 글은 그보다 먼저 별도로 간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ trips: "none" });
  await start(page, "acop_u_known");

  await finishOnboarding(page);
  await page.getByRole("button", { name: "여행 계획 등록하기" }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await checkPlan(page);
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible();

  // 접수까지는 설문이 안 간다 — 서버가 받는 것은 계획 글뿐이다.
  const beforeConfirm = await server.log();
  expect(beforeConfirm.some((entry) => entry.path.endsWith("/confirm"))).toBe(false);
  const [intake] = await server.received("POST", "/v1/web/trip-intakes");
  expect(String(intake.body?.multipart)).not.toContain("survey");

  await page.getByRole("button", { name: "여행 등록" }).click();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));
  const [confirm] = await server.received("POST", "/confirm");
  expect(confirm.body).toEqual({ revision: 1, survey: { version: "2026-09-24.v1", pace: "relaxed", on_disruption: "replace" } });
});

const WEBHOOK = "https://discord.com/api/web" + "hooks/123456789012345678/AbC-def_123456789012345";

test("디스코드 알림 카드의 웹훅은 알림 채널 동의와 함께 약관 단계를 지날 때 서버로 가고(동의를 기록하며 게스트 세션이 이미 생겼다), 브라우저 저장소에는 남지 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ trips: "none" });
  await start(page, null);
  await finishOnboarding(page, async () => {
    const head = page.getByRole("button", { name: /디스코드 알림/ });
    await head.click();
    await page.getByRole("textbox", { name: "디스코드 웹훅 URL" }).fill(WEBHOOK);
    await head.click();                                              // fold it; the terms step checks the field and passes
    await expect(head).toContainText("입력했어요 · 마이페이지에서 바꿀 수 있어요");
  }, ["alert_channel"]);                                             // ★알림 채널 정보는 그 선택 동의를 해야 보낸다(`alert_channel`)
  // ★`[2026-10-05]` Agreeing to the terms records the consent on the server, which makes the guest session; the webhook (agreed to as the alert-channel item) goes up right behind it:
  //   no waiting in page memory for a first plan any more. Once, with the cookie and the CSRF token, no key.
  await expect.poll(async () => (await server.received("PUT", "/v1/web/profile")).map((entry) => [entry.session, entry.key, entry.body])).toEqual([["stub-session-1", null, { discord_webhook_url: WEBHOOK }]]);
  await page.getByRole("button", { name: "여행 계획 등록하기" }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await checkPlan(page);
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible();
  expect(await server.received("PUT", "/v1/web/profile")).toHaveLength(1);                           // 등록 때 다시 보내지 않는다
  const token = WEBHOOK.split("/").pop() ?? "";
  expect(await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }))).not.toContain(token);
});

test("세션이 이미 있으면 웹훅은 알림 채널 동의와 함께 약관 단계를 지날 때 서버로 가고, 동의하지 않으면 입력한 주소는 버려지며, 비워 두면 저장된 웹훅을 건드리지 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page, "acop_u_known");
  await finishOnboarding(page, async () => {
    const head = page.getByRole("button", { name: /디스코드 알림/ });
    await head.click();
    await page.getByRole("textbox", { name: "디스코드 웹훅 URL" }).fill(WEBHOOK);
    await head.click();
  }, ["alert_channel"]);
  await expect.poll(async () => (await server.received("PUT", "/v1/web/profile")).map((entry) => entry.body)).toEqual([{ discord_webhook_url: WEBHOOK }]);

  // Back on the card with the field cleared: leaving it again sends nothing (blank is "not entered", not "remove").
  await page.goto("/start");
  const head = page.getByRole("button", { name: /디스코드 알림/ });
  await head.click();
  await expect(page.getByRole("textbox", { name: "디스코드 웹훅 URL" })).toHaveValue("");
  await head.click();
  await page.getByRole("button", { name: /약관 동의/ }).click();
  expect(await server.received("PUT", "/v1/web/profile")).toHaveLength(1);
  const token = WEBHOOK.split("/").pop() ?? "";
  expect(await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }))).not.toContain(token);
});

test("설문을 마친 뒤 새로고침해도 답이 남아, 등록 화면이 그 답을 이어받고 설문이 서버로 간다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page, "acop_u_known");
  await finishOnboarding(page);
  await page.goto("/trips/new");                 // 새로고침과 같다 — 2026-10-01 부터 답은 이 브라우저에 남는다
  await expect(page.getByText("함께 고른 여행 취향")).toBeVisible();
  await expect(page.getByText("취향 설문을 마치지 않아서", { exact: false })).toHaveCount(0);
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await checkPlan(page);
  await page.getByRole("button", { name: "여행 등록" }).click();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));
  const [confirm] = await server.received("POST", "/confirm");
  expect(confirm.body).toEqual({ revision: 1, survey: { version: "2026-09-24.v1", pace: "relaxed", on_disruption: "replace" } });
});

test("설문을 마치지 않았으면 등록 화면이 그 사실을 알리고, 등록은 되지만 취향 칸은 서버로 가지 않는다(계획 담기에서 정한 여유·항로 지킴이만 간다)", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page, "acop_u_known");
  await page.goto("/trips/new");
  await expect(page.getByText("취향 설문을 마치지 않아서 이번 등록에는 취향이 반영되지 않아요", { exact: false })).toBeVisible();
  await expect(page.getByRole("link", { name: "취향 설정하기" })).toHaveAttribute("href", "/start");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await checkPlan(page);
  await page.getByRole("button", { name: "여행 등록" }).click();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));
  const [confirm] = await server.received("POST", "/confirm");
  expect(confirm.body).toEqual({ revision: 1, survey: { version: "2026-09-24.v1", pace: "moderate", on_disruption: "replace" } });
});

test("글에서 일정을 한 줄도 못 읽으면 옛 확인 화면 대신 짧은 안내와 등록 화면으로 가는 링크만 나온다(짜 달라는 말을 읽었으면 「계획 짜 주기」를 권한다)", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ intake: "empty_plan" });
  await start(page);
  await openRegistration(page);
  await page.getByLabel("나의 여행 계획").fill("서울 이틀 조용한 곳으로 짜 주세요");
  await checkPlan(page);

  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);
  await expect(page.getByRole("heading", { name: "이 글에서는 일정을 찾지 못했어요" })).toBeVisible();
  await expect(page.getByText("글에서 일정을 짜 달라는 요청은 읽었어요", { exact: false })).toBeVisible();
  await expect(page.getByRole("link", { name: "등록 화면으로" })).toHaveAttribute("href", "/trips/new");
  // 옛 화면의 「대신 짜 드릴까요?」 칸과 그 입력들은 없다 — 일정 짜기는 등록 화면의 세 번째 칸이 한다
  await expect(page.getByRole("heading", { name: /일정을 짜 달라고 하셨어요|대신 짜 드릴까요/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /이 조건으로 짜서 등록/ })).toHaveCount(0);
  await expect(page.getByLabel("첫날")).toHaveCount(0);
  expect(await server.received("POST", "/plan")).toHaveLength(0);
});

test("아무것도 넣지 않고 「계획 확인하기」를 누르면 입력칸 아래에 이유가 뜨고 초점이 그리 가며, 쓰기 시작하면 사라지고, 서버로는 아무것도 가지 않는다", async ({ page, request }) => {
  // ★2026-10-03 사용자 결정 — 고른 칸이 비어 있으면 못 넘어간다. ★2026-10-06 사용자 지시 — 단추를 꺼 두지 않고, 누르면 이유를 말한다.
  const server = mockServer(request);
  await start(page);
  await openRegistration(page);
  const send = page.getByRole("button", { name: "계획 확인하기" });
  await expect(send).not.toHaveAttribute("disabled");
  await send.click({ force: true });
  await expect(page.getByRole("alert").filter({ hasText: "여행 계획을 적거나 파일을 올려 주세요." })).toBeVisible();
  await expect(page.getByLabel("나의 여행 계획")).toBeFocused();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  // 단추를 거치지 않는 제출도 같다 — 글칸에서 Enter 는 줄바꿈일 뿐 폼을 보내지 않으므로, 제출 이벤트를 직접 보낸다(코덱스 검토 2026-10-03)
  await page.locator("form").dispatchEvent("submit");
  await expect(page).toHaveURL(/\/trips\/new$/);
  expect(await server.received("POST", "/v1/web/trip-intakes")).toHaveLength(0);
  // 공백뿐이어도 비어 있는 것이다
  await page.getByLabel("나의 여행 계획").fill("  \n  ");
  await send.click({ force: true });
  await expect(page.getByRole("alert").filter({ hasText: "여행 계획을 적거나 파일을 올려 주세요." })).toBeVisible();
  await page.getByLabel("나의 여행 계획").fill("경복궁");                                                // 쓰기 시작하면 이유가 사라진다
  await expect(page.locator("#plan-error")).toHaveCount(0);
  await send.click({ force: true });
  await expect(page.getByRole("dialog")).toBeVisible();                                               // 값이 있으니 항로 지킴이 카드가 열린다(읽기는 아직 시작 전)
  expect(await server.received("POST", "/v1/web/trip-intakes")).toHaveLength(0);
});

test("파일 칸: 고른 파일이 이름·크기 칩으로 보이고, 빼기로 뺄 수 있으며, 남은 파일만 서버로 간다", async ({ page, request }) => {
  // 2026-09-30: 브라우저 기본 「파일 선택」 모양을 앱 디자인으로 바꿨다(코덱스 아스트라 설계). 숨긴 input 은 그대로 쓴다.
  const server = mockServer(request);
  await start(page);
  await page.goto("/trips/new");
  await expect(page.getByText("0 / 5개 선택됨")).toBeVisible();
  await page.locator("#plan-files").setInputFiles([
    { name: "계획표.pdf", mimeType: "application/pdf", buffer: Buffer.from("p".repeat(2048)) },
    { name: "지운다.xlsx", mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", buffer: Buffer.from("x") },
  ]);
  await expect(page.getByText("2 / 5개 선택됨")).toBeVisible();
  await expect(page.getByText("계획표.pdf")).toBeVisible();
  await expect(page.getByText("2 KB")).toBeVisible();
  await page.getByRole("button", { name: "지운다.xlsx 빼기" }).click();
  await expect(page.getByText("1 / 5개 선택됨")).toBeVisible();
  await checkPlan(page);
  await expect.poll(async () => (await server.received("POST", "/v1/web/trip-intakes")).length).toBe(1);
  const [sent] = await server.received("POST", "/v1/web/trip-intakes");
  expect(String(sent.body?.multipart)).toContain('filename="계획표.pdf"');
  expect(String(sent.body?.multipart)).not.toContain("지운다.xlsx");
});

test("서버가 계획을 읽지 못하면 이유를 그대로 보이고 다시 올리는 길을 준다", async ({ page, request }) => {
  await mockServer(request).scenario({ intake: "fatal" });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill("???");
  await checkPlan(page);
  await expect(page.getByRole("heading", { name: "이 계획을 읽지 못했어요" })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "사진에서 글자를 찾지 못했어요" })).toBeVisible();
  await expect(page.getByRole("link", { name: "다시 올리기" })).toHaveAttribute("href", "/trips/new");
});

test("고치는 사이 계획이 바뀌어 서버가 거절해도(409 stale_revision) 화면은 최신 상태를 다시 읽고 깨지지 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page);
  await openRegistration(page);
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await checkPlan(page);
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible();
  await server.scenario({ edits: "stale" });
  const before = (await server.received("GET", "/v1/web/trip-intakes/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")).length;
  await page.getByRole("button", { name: "경복궁 관람 수정" }).click();
  await page.getByRole("searchbox", { name: "장소 검색" }).fill("창덕궁");
  await page.getByRole("button", { name: "「창덕궁」으로 바꾸기" }).click();
  await expect.poll(async () => (await server.received("GET", "/v1/web/trip-intakes/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")).length).toBeGreaterThan(before);
  expect(await server.received("POST", "/edits")).toHaveLength(1);
  await page.getByRole("button", { name: "바꾸기 그만두기" }).click();
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible();
});

test("새 세션 시작이 한도에 걸리면(429) 서버 문장 그대로 알리고 계획 입력은 지켜진다", async ({ page, request }) => {
  await mockServer(request).scenario({ session: "limited" });
  await start(page, null);
  await agree(page);                                                                     // 이 시험의 주제는 세션 한도다 - 약관에는 이미 동의한 사람
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await checkPlan(page);
  await expect(page.getByText("새 세션을 너무 많이 받았다")).toBeVisible();
  await expect(page.getByLabel("나의 여행 계획")).toHaveValue(PLAN);
});

test("계획 짜 주기가 오래 걸리는 동안(실제 서버는 운영시간을 읽느라 1분쯤) 「일정을 짜는 중이에요」가 보이고 되돌아가는 화살표는 없으며, 끝나면 여행 화면으로 간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 0, planDelay: 3000 });
  await start(page);
  await openRegistration(page);
  await fillPlanAsk(page, { start: weekAhead(), days: 2, party: 2 });
  await checkPlan(page);
  await expect(page).toHaveURL(/\/intakes\/starting$/);
  await expect(page.getByRole("heading", { name: "일정을 짜는 중이에요", level: 1 })).toBeVisible();
  // 서버가 일정을 짜는 동안에는 뒤로 가는 화살표를 두지 않는다 — 요청이 이미 나갔다
  await expect(page.getByRole("status").filter({ hasText: "여행으로 등록하는 중이에요" })).toBeVisible();
  await expect(page.getByRole("button", { name: "뒤로" })).toHaveCount(0);
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`), { timeout: 15_000 });
});

test("등록 확인이 서버 오류(500)로 실패하면 오류 문구가 화면 안으로 들어와 보이고, 확인 화면에 그대로 남는다", async ({ page, request }) => {
  await mockServer(request).scenario({ fail: "confirm" });
  await page.setViewportSize({ width: 1280, height: 600 });         // 목록이 길어 오류 칸이 화면 아래에 있는 상황
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await checkPlan(page);
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible();
  await page.getByRole("button", { name: "여행 등록" }).click();
  const alert = page.getByRole("alert").filter({ hasText: "서버 오류" });
  await expect(alert).toBeInViewport();
  await expect(page).toHaveURL(/\/intakes\//);
});

test("읽은 접수를 열면 새 결과 화면이 서버가 찾은 장소와 판정을 보이고, 옛 확인 화면으로 가는 길은 없다", async ({ page, request }) => {
  await mockServer(request).scenario({ readingPolls: 0 });
  await start(page);
  await page.goto("/intakes/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee");
  await expect(page.getByRole("heading", { name: "내 여행", level: 1 })).toBeVisible();            // the server's trip title
  await expect(page.locator("span[class*=headBadge][data-kind=ok]")).toBeVisible();              // 머리에는 ✓ 하나(고칠 곳이 없다)
  const card = page.getByRole("article", { name: "경복궁 관람" });
  await expect(card).not.toContainText("확인 필요");                                                // 괜찮은 일정에는 아무 말도 붙지 않는다
  const head = card.getByRole("heading").getByRole("button");
  await expect(head).toHaveAttribute("aria-expanded", "false");
  await head.click();
  await expect(head).toHaveAttribute("aria-expanded", "true");
  await expect(card.getByText("경복궁", { exact: true })).toBeVisible();                       // the place the server found
  await expect(card.getByText(/운영시간|휴무일/)).toHaveCount(0);                                 // not in the response: not shown
  await expect(page.getByRole("button", { name: "여행 등록" })).not.toHaveAttribute("aria-disabled", "true");
  // 옛 목록형 확인 화면(「이전 확인 화면 열기」 · 「여행 계획 살펴보기」 · 「읽은 원문 전체 보기」)은 없다
  await expect(page.getByRole("button", { name: "이전 확인 화면 열기" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "여행 계획 살펴보기" })).toHaveCount(0);
});

test("서버가 등록을 막는 문제를 주면 카드가 「확인 필요」로 이유를 보이고, 꺼진 「다시 제출」이 고칠 길을 알린다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 0, intake: "blocked" });
  await start(page);
  await page.goto("/intakes/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee");
  const card = page.getByRole("article", { name: "경복궁 관람" });
  await expect(card.getByText("확인 필요")).toBeVisible();
  await expect(needsBadge(page)).toHaveText("!1");
  await card.getByRole("heading").getByRole("button").click();
  await expect(card.getByText("장소를 정하지 못했습니다")).toBeVisible();                      // the server's own message
  await expect(page.getByRole("button", { name: "여행 등록" })).toHaveCount(0);
  const recheck = page.getByRole("button", { name: "다시 제출" });
  await expect(recheck).toHaveAttribute("aria-disabled", "true");
  await recheck.click({ force: true });
  await expect(page.getByRole("status").filter({ hasText: "확인이 필요한 항목 1건이 남아 있어요" })).toBeVisible();
  expect(await server.received("POST", "/confirm")).toHaveLength(0);
});

const INTAKE = "/intakes/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";

test("결과 화면의 수정 화면: 검색이 없는 서버에서는 쓴 이름으로 바꾸고, 그 이름이 서버 수정 계약으로 간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 0 });
  await start(page);
  await page.goto(INTAKE);
  await page.getByRole("button", { name: "경복궁 관람 수정" }).click();
  await expect(page.getByRole("heading", { name: "경복궁 관람 바꾸기" })).toBeVisible();
  await expect(page.getByText("다른 후보가 없어요 · 위 검색창에서 찾아 바꿀 수 있어요")).toBeVisible();
  await expect(page.getByText("등록된 사진이 없어요 · 장소 사진은 준비 중이에요")).toBeVisible();
  await page.getByRole("searchbox", { name: "장소 검색" }).fill("창덕궁");
  await expect(page.getByText("장소 검색은 준비 중이에요.")).toBeVisible();
  await page.getByRole("button", { name: "「창덕궁」으로 바꾸기" }).click();
  await expect(page.getByRole("status").filter({ hasText: "경복궁 관람을 창덕궁으로 바꿨어요" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "경복궁 관람 바꾸기" })).toHaveCount(0);
  const [edit] = await server.received("POST", "/edits");
  expect(edit.body).toEqual({ revision: 1, edits: [{ source_id: "s1", field: "items[0].place", value: { name: "창덕궁" } }] });
});

test("결과 화면의 「직접 고치기」: 서버가 장소를 못 찾으면(422) 서버 문장을 보이고 입력을 그대로 두며, 그만두면 수정 단추로 돌아간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 0, edits: "not_found" });
  await start(page);
  await page.goto(INTAKE);
  await page.getByRole("button", { name: "경복궁 관람 수정" }).click();
  await page.getByText("직접 고치기 · 이름·날짜·시각·장소 없음").click();
  const editor = page.getByRole("form", { name: "「경복궁 관람」 고치기" });
  await editor.getByRole("searchbox", { name: "장소 이름" }).fill("없는 곳");
  await editor.getByRole("button", { name: "저장" }).click();
  await expect(editor.getByRole("alert")).toHaveText("「없는 곳」: 이 이름으로 장소를 찾지 못했어요");
  await expect(editor.getByRole("searchbox", { name: "장소 이름" })).toHaveValue("없는 곳");
  // Leaving sends nothing more and comes back to the card's edit button.
  await editor.getByRole("button", { name: "취소" }).click();
  await page.getByRole("button", { name: "바꾸기 그만두기" }).click();
  await expect(page.getByRole("button", { name: "경복궁 관람 수정" })).toBeFocused();
  expect(await server.received("POST", "/edits")).toHaveLength(1);
});

test("결과 화면의 삭제: 바로 지우지 않고 회색으로 표시한 뒤 되돌리기 자리가 서며, 「다시 제출」을 누르면 빼기가 서버로 간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 0 });
  await start(page);
  await page.goto(INTAKE);
  await page.getByRole("button", { name: "경복궁 관람 삭제" }).click();
  const card = page.getByRole("article", { name: "경복궁 관람" });
  await expect(card).toContainText("삭제 예정");
  await expect(page.getByRole("button", { name: "경복궁 관람 삭제 되돌리기" })).toBeVisible();        // 휴지통이 있던 자리
  expect(await server.received("POST", "/edits")).toHaveLength(0);                                     // 묻지도 보내지도 않았다
  await page.getByRole("button", { name: "다시 제출" }).click();
  await expect.poll(async () => (await server.received("POST", "/edits")).length).toBe(1);
  const [edit] = await server.received("POST", "/edits");
  expect(edit.body).toEqual({ revision: 1, edits: [{ source_id: "s1", field: "items[0].removed", value: true }] });
});

test("결과 화면: 서버에 아직 없는 잠금·자동 추천·전체 자동 추천은 화면에 남아 누르면 「준비 중」이라고 말한다", async ({ page, request }) => {
  await mockServer(request).scenario({ readingPolls: 0 });
  await start(page);
  await page.goto(INTAKE);
  const say = (text: string) => page.getByRole("status").filter({ hasText: text });
  await page.getByRole("article", { name: "경복궁 관람" }).getByRole("heading").getByRole("button").click();
  const lock = page.getByRole("button", { name: "경복궁 관람 꼭 넣을 일정으로 고정" });
  await expect(lock).toHaveAttribute("aria-disabled", "true");
  await lock.click({ force: true });
  await expect(say("잠금은 준비 중이에요")).toBeVisible();
  await page.getByRole("button", { name: "경복궁 관람 자동 추천", exact: true }).click({ force: true });
  await expect(say("자동 추천은 준비 중이에요")).toBeVisible();
  const all = page.getByRole("button", { name: /전체 자동 추천/ });
  await expect(all).toHaveAttribute("aria-disabled", "true");
  await all.click({ force: true });
  await expect(say("전체 자동 추천은 준비 중이에요")).toBeVisible();
});

test("결과 화면: 서버가 여행 첫날을 물으면 입력칸이 나오고, 저장하면 여행 칸 수정이 서버로 간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 0 });
  await page.route("**/v1/web/trip-intakes/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", async (route) => {
    const response = await route.fetch();
    const view = await response.json();
    view.check.ready = false;
    view.check.problems = [{ source_id: null, field: "trip.first_day", code: "no_date", message: "여행 첫날을 알려 주세요" }];
    await route.fulfill({ response, json: view });
  });
  await start(page);
  await page.goto(INTAKE);
  const panel = page.getByRole("region", { name: "여행 전체에서 확인할 것" });
  await expect(panel).toContainText("여행 첫날을 알려 주세요");
  await expect(page.getByRole("button", { name: "여행 등록" })).toBeDisabled();
  await panel.getByLabel("여행 첫날").fill("2026-10-12");
  await panel.getByRole("button", { name: "저장" }).click();
  await expect.poll(async () => (await server.received("POST", "/edits")).length).toBe(1);
  expect((await server.received("POST", "/edits"))[0].body).toEqual({ revision: 1, edits: [{ field: "trip.first_day", value: "2026-10-12" }] });
});
