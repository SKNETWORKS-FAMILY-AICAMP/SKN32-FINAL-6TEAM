import { expect, test } from "@playwright/test";
import { finishOnboarding, start, mockServer, TRIP_ID } from "./helpers";

const PLAN = "10/1 09:00 경복궁 관람";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

test("첫 방문: 계획을 올리면 키가 발급되고 안내가 한 번만 보이며, 읽은 결과를 확인해 등록하면 여행 화면으로 간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ trips: "none" });
  await start(page, null);

  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);

  // 읽는 중 → 확인 화면. 서버가 읽은 항목이 그대로 보인다.
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible();
  await page.getByText("읽은 원문 전체 보기", { exact: true }).click();
  await expect(page.getByText("10/1 09:00 경복궁 관람").first()).toBeVisible();

  // 키가 방금 발급됐다: 서버의 안내 문장과 함께 한 번 보이고, 「따로 보관했어요」로 닫힌다.
  const notice = page.getByRole("status").filter({ hasText: "내 여행 열쇠를 따로 보관해 주세요" });
  await expect(notice).toBeVisible();
  await expect(notice).toContainText("다시 보여 드리지 않아요");
  await expect(notice.getByRole("textbox")).toHaveValue(/^acop_u_stub_1$/);
  await notice.getByRole("button", { name: "따로 보관했어요" }).click();
  await expect(notice).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible();
  await expect(page.getByText("내 여행 열쇠를 따로 보관해 주세요")).toHaveCount(0);

  await page.getByRole("button", { name: "여행 등록" }).click();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));
  await expect(page.getByRole("heading", { name: "나의 여행", exact: true })).toBeVisible();

  // 서버가 실제로 받은 것: 계획 글은 접수 때, 확인은 등록할 때. 설문을 안 마쳤으니 설문 칸은 아예 없다.
  const [intake] = await server.received("POST", "/v1/web/trip-intakes");
  expect(String(intake.body?.multipart)).toContain(PLAN);
  const [confirm] = await server.received("POST", "/confirm");
  expect(confirm.body).toEqual({ revision: 1 });
  expect(confirm.key).toBe("acop_u_stub_1");
});

test("서버가 읽는 동안 새 계획 확인 화면이 서버의 원문 줄을 읽는 중으로 보이고, 읽기가 끝나면 확인 화면으로 넘어간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 3 });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);

  // Reading: the server's own line, not yet read; the bar and the back arrow of the new screen.
  await expect(page.getByRole("heading", { name: "계획을 확인하고 있어요", level: 1 })).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "계획 확인 진행" })).toBeVisible();
  const line = page.getByRole("listitem").filter({ hasText: "10/1 09:00 경복궁 관람" });
  await expect(line).toContainText("읽는 중");

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
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible();

  // 접수까지는 설문이 안 간다 — 서버가 받는 것은 계획 글뿐이다.
  const beforeConfirm = await server.log();
  expect(beforeConfirm.some((entry) => entry.path.endsWith("/confirm"))).toBe(false);
  const [intake] = await server.received("POST", "/v1/web/trip-intakes");
  expect(String(intake.body?.multipart)).not.toContain("survey");

  await page.getByRole("button", { name: "여행 등록" }).click();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));
  const [confirm] = await server.received("POST", "/confirm");
  expect(confirm.body).toEqual({ revision: 1, survey: { version: "2026-09-24.v1", pace: "relaxed" } });
});

const WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/AbC-def_123456789012345";

test("알림·복구 카드의 디스코드 웹훅은 등록까지 가도 서버로 보내지 않고 이 브라우저 저장소에도 남기지 않는다 — 저장 연결은 백엔드 몫", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ trips: "none" });
  await start(page, "acop_u_known");
  await finishOnboarding(page, async () => {
    const head = page.getByRole("button", { name: /알림·복구/ });
    await head.click();
    await page.getByRole("textbox", { name: "디스코드 웹훅 URL" }).fill(WEBHOOK);
    await head.click();                                              // fold it; the terms step checks the field and passes
    await expect(head).toContainText("입력했어요 · 웹훅은 아직 저장하지 않아요");
  });
  await page.getByRole("button", { name: "여행 계획 등록하기" }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible();
  await page.getByRole("button", { name: "여행 등록" }).click();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));

  // The webhook carries a token: it is in no request the server received, and not in this browser's storage.
  const token = WEBHOOK.split("/").pop() ?? "";
  expect(JSON.stringify(await server.log())).not.toContain(token);
  expect(await page.evaluate(() => JSON.stringify({ ...localStorage }))).not.toContain(token);
});

test("설문을 마친 뒤 새로고침해도 답이 남아, 등록 화면이 그 답을 이어받고 설문이 서버로 간다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page, "acop_u_known");
  await finishOnboarding(page);
  await page.goto("/trips/new");                 // 새로고침과 같다 — 2026-10-01 부터 답은 이 브라우저에 남는다
  await expect(page.getByText("함께 고른 여행 취향")).toBeVisible();
  await expect(page.getByText("취향 설문을 마치지 않아서", { exact: false })).toHaveCount(0);
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await page.getByRole("button", { name: "여행 등록" }).click();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));
  const [confirm] = await server.received("POST", "/confirm");
  expect(confirm.body).toEqual({ revision: 1, survey: { version: "2026-09-24.v1", pace: "relaxed" } });
});

test("설문을 마치지 않았으면 등록 화면이 그 사실을 알리고, 등록은 되지만 설문 칸은 서버로 가지 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page, "acop_u_known");
  await page.goto("/trips/new");
  await expect(page.getByText("취향 설문을 마치지 않아서 이번 등록에는 취향이 반영되지 않아요", { exact: false })).toBeVisible();
  await expect(page.getByRole("link", { name: "취향 설정하기" })).toHaveAttribute("href", "/start");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await page.getByRole("button", { name: "여행 등록" }).click();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));
  const [confirm] = await server.received("POST", "/confirm");
  expect(confirm.body).toEqual({ revision: 1 });
});

test("일정을 못 읽으면 일정 짜기 칸이 나오고, 확인한 조건이 일정 짜기 요청으로 간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ intake: "empty_plan" });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill("서울 이틀 조용한 곳으로 짜 주세요");
  await page.getByRole("button", { name: "계획 확인하기" }).click();

  await expect(page.getByRole("heading", { name: "일정을 짜 달라고 하셨어요" })).toBeVisible();
  await expect(page.getByLabel("첫날")).toHaveValue("2026-10-01");
  await expect(page.getByLabel("일수")).toHaveValue("2");
  await expect(page.getByLabel("인원")).toHaveValue("2");
  await page.getByRole("button", { name: /이 조건으로 짜서 등록/ }).click();

  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));
  const [plan] = await server.received("POST", "/plan");
  expect(plan.body).toEqual({ revision: 1, start_date: "2026-10-01", days: 2, party_size: 2, keep_read_items: false });
});

test("계획을 비워 두고 「계획 확인하기」를 누르면 오류 없이 다음 화면(대신 짜 드릴까요?)으로 넘어간다", async ({ page, request }) => {
  // ★2026-09-30 사용자 결정 — 빈 계획은 오류가 아니라 짜기로 이어진다. 서버는 빈 접수를 「짜 달라는 요청」으로 받는다.
  const server = mockServer(request);
  await server.scenario({ intake: "empty_plan" });
  await start(page);
  await page.goto("/trips/new");
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page.getByRole("heading", { name: "일정을 짜 달라고 하셨어요" })).toBeVisible();
  await expect(page.locator("#main-content").getByText("시간과 장소가 있는 여행 계획을 입력해 주세요.")).toHaveCount(0);
  const [sent] = await server.received("POST", "/v1/web/trip-intakes");
  // 가짜 문장을 넣지 않는다 — 여러 부분 양식의 text 칸이 비어 있다
  expect(String(sent.body?.multipart)).toMatch(new RegExp(String.raw`name="text"\r\n\r\n\r\n--`));
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
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect.poll(async () => (await server.received("POST", "/v1/web/trip-intakes")).length).toBe(1);
  const [sent] = await server.received("POST", "/v1/web/trip-intakes");
  expect(String(sent.body?.multipart)).toContain('filename="계획표.pdf"');
  expect(String(sent.body?.multipart)).not.toContain("지운다.xlsx");
});

test("확인 화면에서 장소를 고치면 고친 값이 서버로 간다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible();

  await page.getByRole("button", { name: /경복궁 관람.*펼쳐서 고치기/ }).click();
  await page.getByPlaceholder("다른 장소로 고치기").fill("창덕궁");
  await page.getByRole("button", { name: "저장하고 확인" }).click();
  await expect.poll(async () => (await server.received("POST", "/edits")).length).toBe(1);
  const [edit] = await server.received("POST", "/edits");
  expect(edit.body).toEqual({ revision: 1, edits: [{ source_id: "s1", field: "items[0].place", value: { name: "창덕궁" } }] });
});

test("서버가 계획을 읽지 못하면 이유를 그대로 보이고 다시 올리는 길을 준다", async ({ page, request }) => {
  await mockServer(request).scenario({ intake: "fatal" });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill("???");
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page.getByRole("heading", { name: "이 계획을 읽지 못했어요" })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "사진에서 글자를 찾지 못했어요" })).toBeVisible();
  await expect(page.getByRole("link", { name: "다시 올리기" })).toHaveAttribute("href", "/trips/new");
});

test("고치는 사이 계획이 바뀌어 서버가 거절해도(409 stale_revision) 화면은 최신 상태를 다시 읽고 깨지지 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible();
  await server.scenario({ edits: "stale" });
  const before = (await server.received("GET", "/v1/web/trip-intakes/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")).length;
  await page.getByRole("button", { name: /경복궁 관람.*펼쳐서 고치기/ }).click();
  await page.getByPlaceholder("다른 장소로 고치기").fill("창덕궁");
  await page.getByRole("button", { name: "저장하고 확인" }).click();
  await expect.poll(async () => (await server.received("GET", "/v1/web/trip-intakes/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")).length).toBeGreaterThan(before);
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible();
});

test("새 키 발급이 한도에 걸리면(429) 서버 문장 그대로 알리고 계획 입력은 지켜진다", async ({ page, request }) => {
  await mockServer(request).scenario({ session: "limited" });
  await start(page, null);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page.getByText("새 키를 너무 많이 받았다")).toBeVisible();
  await expect(page.getByLabel("나의 여행 계획")).toHaveValue(PLAN);
});

test("일정 짜기가 오래 걸리는 동안(실제 서버는 운영시간을 읽느라 1분쯤) 단추가 잠기고 「짜는 중」이 보이며, 끝나면 여행 화면으로 간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ intake: "empty_plan", planDelay: 3000 });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill("서울 이틀");
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await page.getByRole("button", { name: /이 조건으로 짜서 등록/ }).click();
  const busy = page.getByRole("button", { name: /짜는 중/ });
  await expect(busy).toBeVisible();
  await expect(busy).toBeDisabled();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`), { timeout: 15_000 });
});

test("등록 확인이 서버 오류(500)로 실패하면 오류 문구가 화면 안으로 들어와 보이고, 확인 화면에 그대로 남는다", async ({ page, request }) => {
  await mockServer(request).scenario({ fail: "confirm" });
  await page.setViewportSize({ width: 1280, height: 600 });         // 목록이 길어 오류 칸이 화면 아래에 있는 상황
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible();
  await page.getByRole("button", { name: "여행 등록" }).click();
  const alert = page.getByRole("alert").filter({ hasText: "서버 오류" });
  await expect(alert).toBeInViewport();
  await expect(page).toHaveURL(/\/intakes\//);
});
