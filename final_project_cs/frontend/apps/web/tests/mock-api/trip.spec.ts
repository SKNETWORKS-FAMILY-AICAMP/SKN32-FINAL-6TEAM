import { expect, test } from "@playwright/test";
import { start, mockServer, TRIP_ID } from "./helpers";

test.beforeEach(async ({ page, request }) => {
  await mockServer(request).reset();
  await start(page);
});

const openTrip = async (page: import("@playwright/test").Page) => {
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(page.getByRole("heading", { name: "나의 여행", exact: true })).toBeVisible();
};

test("여행 화면은 서버가 준 일정·고정·다른 안·알림·이력·경고·계획서 링크를 그대로 보이고, 이동 항목은 목록에 섞지 않는다", async ({ page }) => {
  await openTrip(page);
  await expect(page.getByText("2일 · 4개 일정")).toBeVisible();                       // 이동 1건은 일정 수에서 빠진다
  const schedule = page.locator("#trip-pane-schedule");
  await expect(schedule.getByText("아침 식당")).toBeVisible();
  await expect(schedule.getByText("11:10 출발").first()).toBeHidden();                // 이동은 다음 일정 메모로 접힌다
  // 구간 길찾기 — 서버가 준 구간(아침 → 경복궁)에만 링크가 있고, 링크가 없는 구간에는 없다
  await expect(schedule.getByRole("link", { name: "지도 앱에서 길찾기" })).toHaveCount(1);
  await expect(schedule.getByRole("link", { name: "지도 앱에서 길찾기" })).toHaveAttribute("href", "https://www.google.com/maps/dir/?api=1&origin=a&destination=b&travelmode=transit");

  // 고정한 일정 표시와 서버가 남겨 둔 다른 안
  await expect(page.locator("#stop-button-i-b").getByText("고정한 일정")).toBeVisible();
  await page.locator("#stop-button-i-b").click();
  await expect(page.locator("#stop-detail-i-b")).toContainText("다른 안");
  await expect(page.locator("#stop-detail-i-b")).toContainText("창덕궁");
  await expect(page.locator("#stop-detail-i-b")).not.toContainText("주소");           // 서버가 장소 사실을 안 보냈으면 줄 자체가 없다
  await expect(page.locator("#stop-detail-i-b").getByRole("button", { name: "이 일정 질문하기" })).toBeVisible();   // 상세가 열려 있는데
  await expect(page.locator("#stop-detail-i-b").getByRole("link", { name: "지도 앱으로 열기" })).toHaveCount(0);  // 지도 링크가 없으면 단추도 없다

  // 서버가 보낸 장소 사실(요식 원장) — 주소·전화·분류·영업시간·미쉐린·편의
  await page.locator("#stop-button-i-a").click();
  const detail = page.locator("#stop-detail-i-a");
  for (const text of ["서울특별시 종로구 율곡로1길 7", "02-000-0000", "한식", "월 08:00–21:00", "셀렉티드 (2026)", "카드 결제"]) await expect(detail).toContainText(text);
  await expect(detail).not.toContainText("michelin_selected");
  // 지도 앱으로 열기 — 서버가 준 구글 지도 링크를 새 창으로(서버가 링크를 안 준 일정에는 단추가 없다)
  await expect(detail.getByRole("link", { name: "지도 앱으로 열기" })).toHaveAttribute("href", "https://www.google.com/maps/search/?api=1&query=%EC%95%84%EC%B9%A8");
  await expect(detail.getByRole("link", { name: "지도 앱으로 열기" })).toHaveAttribute("target", "_blank");

  // 서버가 찾은 것·보낸 것·바꾼 것
  await expect(page.getByRole("heading", { name: "살펴볼 점" })).toBeVisible();
  await expect(page.getByText("하루가 빡빡해요")).toBeVisible();
  await expect(page.getByText("일정을 줄이세요")).toBeVisible();
  const notices = page.locator("details").filter({ hasText: "받은 알림" });
  await notices.locator("summary").click();
  await expect(notices).toContainText("오늘 첫 일정은 08:00 아침 식당이에요.");
  await expect(notices).toContainText("2개");
  const history = page.locator("details").filter({ hasText: "변경 이력" });
  await history.locator("summary").click();
  await expect(history).toContainText("처음 등록");

  // 여행계획서 링크, 실제 수정 경로, 데모 잔재가 없다
  const plan = page.getByRole("link", { name: "여행계획서 열기" });
  await expect(plan).toHaveAttribute("href", new RegExp(`/plan/${TRIP_ID}\\?t=`));
  await expect(plan).toHaveAttribute("target", "_blank");
  await expect(page.getByRole("link", { name: "새 계획 올리기" })).toHaveAttribute("href", "/trips/new");
  await expect(page.getByRole("link", { name: "일정 수정" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "검증 결과 다시 보기" })).toHaveCount(0);
  await expect(page.getByText("서버에 연결된 화면이에요")).toBeVisible();
});

test("경고와 알림이 없으면 그 칸을 그리지 않는다(빈 칸이나 0을 지어내지 않는다)", async ({ page, request }) => {
  await mockServer(request).scenario({ warnings: "none", notices: "none" });
  await openTrip(page);
  await expect(page.getByRole("heading", { name: "살펴볼 점" })).toHaveCount(0);
  await expect(page.locator("details").filter({ hasText: "받은 알림" })).toHaveCount(0);
});

test("서버가 기다리는 선택이 있으면 「선택이 필요해요」가 뜨고, 고르면 그 안의 key 가 서버로 가고 칸이 사라진다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ proposals: "open" });
  await openTrip(page);
  const ask = page.getByRole("region", { name: /선택이 필요해요/ });
  await expect(ask).toBeVisible();
  await expect(ask).toContainText("점심 식당이 문을 닫았어요. 대체 식당을 골라 주세요.");   // 서버 통지 문장 그대로
  await expect(ask).toContainText("12:00 · 점심 식당");
  await ask.getByRole("button", { name: /대체 식당 A/ }).click();

  await expect.poll(async () => (await server.received("POST", "/choose")).length).toBe(1);
  const [choose] = await server.received("POST", "/choose");
  expect(choose.body).toEqual({ key: "o-1" });
  await expect(page.getByRole("region", { name: /선택이 필요해요/ })).toHaveCount(0);
  await expect(page.getByText("고르신 곳으로 일정을 바꿨어요.")).toBeVisible();          // 칸이 사라져도 결과는 말한다
});

test("실내·야외를 모르는 일정의 「바꿀까요?」: 「바꿔 줘」가 key change 를 보내고, 서버가 채운 다른 곳을 다시 읽어 보인다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ proposals: "consent" });
  await openTrip(page);
  const ask = page.getByRole("region", { name: /선택이 필요해요/ });
  await expect(ask.getByRole("button", { name: "바꿔 줘 — 다른 곳 보기" })).toBeVisible();
  await ask.getByRole("button", { name: "바꿔 줘 — 다른 곳 보기" }).click();
  await expect.poll(async () => (await server.received("POST", "/choose")).length).toBe(1);
  expect((await server.received("POST", "/choose"))[0].body).toEqual({ key: "change" });
  await expect(ask.getByRole("button", { name: /실내 박물관/ })).toBeVisible();              // 같은 제안을 다시 읽었다
  await expect(ask.getByRole("button", { name: "바꿔 줘 — 다른 곳 보기" })).toHaveCount(0);  // 선택지가 생기면 물음은 사라진다
  await expect(page.getByText("다른 곳을 찾았어요 — 위에서 골라 주세요.")).toBeVisible();
});

test("「바꿔 줘」에 다른 곳이 없으면 원래 일정을 그대로 둔다고 알린다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ proposals: "consent", choose: "no_alternate" });
  await openTrip(page);
  await page.getByRole("button", { name: "바꿔 줘 — 다른 곳 보기" }).click();
  await expect(page.getByText("바꿀 수 있는 다른 곳을 찾지 못했어요 — 원래 일정을 그대로 둡니다.")).toBeVisible();
});

test("자동으로 바꾼 일정은 「되돌리기」로 서버가 준 값 그대로 되돌리고, 서버의 답을 보인다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ undo: "open" });
  await openTrip(page);
  const card = page.getByRole("region", { name: "자동으로 바꾼 일정" });
  await expect(card).toContainText("비 소식이 있어 09:30 경복궁 관람을 실내 박물관으로 바꿨어요.");
  await card.getByRole("button", { name: "되돌리기" }).click();
  await expect.poll(async () => (await server.received("POST", "/rollback")).length).toBe(1);
  expect((await server.received("POST", "/rollback"))[0].body).toEqual({ request_id: "rollback:v1->v0", base_version: 1, to_version: 0 });
  await expect(page.getByText("09:30 일정을 원래대로(경복궁 관람) 되돌렸어요.")).toBeVisible();
  await expect(page.getByRole("region", { name: "자동으로 바꾼 일정" })).toHaveCount(0);   // 되돌린 뒤엔 칸이 없다
});

test("그 사이 일정이 또 바뀌어 되돌리기가 거절되면(409) 아무것도 안 바뀌었다고 알린다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ undo: "stale" });
  await openTrip(page);
  await page.getByRole("region", { name: "자동으로 바꾼 일정" }).getByRole("button", { name: "되돌리기" }).click();
  await expect(page.getByText("그 사이 일정이 다시 바뀌어 되돌리지 않았어요. 지금 상태를 다시 불러왔어요.")).toBeVisible();
});

test("「지금 일정 그대로 두기」는 key 를 null 로 보낸다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ proposals: "open" });
  await openTrip(page);
  await page.getByRole("button", { name: "지금 일정 그대로 두기" }).click();
  await expect.poll(async () => (await server.received("POST", "/choose")).length).toBe(1);
  expect((await server.received("POST", "/choose"))[0].body).toEqual({ key: null });
});

test("이미 정해진 선택(409)은 「아무것도 바뀌지 않았다」고 알리고 서버 상태를 다시 읽는다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ proposals: "open", choose: "conflict" });
  await openTrip(page);
  await page.getByRole("button", { name: /대체 식당 B/ }).click();
  await expect(page.getByRole("alert").filter({ hasText: "이미 정해졌거나" })).toContainText("아무것도 바뀌지 않았고");
  // 알림 뒤에 화면이 서버를 다시 읽는다
  await expect.poll(async () => (await server.received("GET", "/proposals")).length).toBeGreaterThan(1);
});

test("지도 탭은 서버 좌표가 있는 일정만 방문 순서로 그린다", async ({ page }) => {
  await openTrip(page);
  await page.getByRole("button", { name: "방문 순서", exact: true }).click();
  const map = page.locator("#trip-pane-map");
  await expect(map.getByRole("button", { name: "1. 아침 식당" })).toBeVisible();
  await expect(map.getByRole("button", { name: "2. 경복궁 관람" })).toBeVisible();
  await expect(map.getByRole("button", { name: "3. 점심 식당" })).toBeVisible();
});

test("채팅: 빠른 질문 세 개와 일정 상세가 화면 문장 그대로 서버로 가고, 서버 답이 그대로 보인다", async ({ page, request }) => {
  const server = mockServer(request);
  await openTrip(page);
  await page.getByRole("button", { name: "채팅", exact: true }).click();
  const chat = page.locator("#trip-pane-chat");
  const last = () => chat.locator("article[data-role=assistant]").last();

  await chat.getByRole("button", { name: "하루 요약" }).click();
  await expect(last()).toContainText("서버 답: 2026-10-01 하루 일정을 요약해 주세요.");
  await chat.getByRole("button", { name: "예약 표시" }).click();
  await expect(last()).toContainText("서버 답: 2026-10-01 예약 표시를 알려 주세요.");

  // 일정을 고른 뒤: 「선택 일정」(상세)·「다음 일정」
  await page.getByRole("button", { name: "일정", exact: true }).click();
  await page.locator("#stop-button-i-b").click();
  await page.getByRole("button", { name: "채팅", exact: true }).click();
  await chat.getByRole("button", { name: "선택 일정" }).click();
  await expect(last()).toContainText("서버 답: 2026-10-01 09:30 경복궁 관람 일정의 상세를 알려 주세요.");
  await chat.getByRole("button", { name: "다음 일정" }).click();
  await expect(last()).toContainText("서버 답: 2026-10-01 09:30 경복궁 관람 다음 일정을 알려 주세요.");

  const sent = (await server.received("POST", "/messages")).map((entry) => entry.body?.message);
  expect(sent).toEqual([
    "2026-10-01 하루 일정을 요약해 주세요.", "2026-10-01 예약 표시를 알려 주세요.",
    "2026-10-01 09:30 경복궁 관람 일정의 상세를 알려 주세요.", "2026-10-01 09:30 경복궁 관람 다음 일정을 알려 주세요.",
  ]);
  // 요청마다 다른 request_id — 서버가 「같은 요청」으로 착각하지 않는다
  const ids = (await server.received("POST", "/messages")).map((entry) => entry.body?.request_id);
  expect(new Set(ids).size).toBe(4);
  // ★서버가 대화를 기록하고 화면이 그 기록을 읽어도 답은 한 번씩만 보인다(기록 시각이 받은 시각보다 이르다) —
  //   2026-09-29 실서버에서 모든 답이 두 번 보였다. 새로고침 뒤에도 같다.
  const answers = async () => chat.locator("article[data-role=assistant] p:nth-child(2)").allInnerTexts();
  expect((await answers()).filter((text) => text.startsWith("서버 답:"))).toHaveLength(4);
  await page.reload();
  await page.getByRole("button", { name: "채팅", exact: true }).click();
  await expect.poll(async () => (await answers()).filter((text) => text.startsWith("서버 답:")).length).toBe(4);
});

test("직접 쓴 질문도 보내고, 옛 서버처럼 answer 없이 escalated 만 오면 화면이 「담당자에게 넘겼어요」를 지어내지 않는다", async ({ page, request }) => {
  await mockServer(request).scenario({ chat: "escalated_bare" });
  await openTrip(page);
  await page.getByRole("button", { name: "채팅", exact: true }).click();
  const chat = page.locator("#trip-pane-chat");
  await chat.getByPlaceholder("일정에 대해 궁금한 점을 입력하세요").fill("뭐라고요?");
  await chat.getByRole("button", { name: "메시지 전송" }).click();
  const reply = chat.locator("article[data-role=assistant]").last();
  await expect(reply).toContainText("escalated");
  await expect(reply).not.toContainText("담당자");
});

test("검증 결과·진행 주소로 들어가면 지어낸 0 대신 「검증 단계가 따로 없다」는 안내와 여행 화면 링크가 나온다", async ({ page }) => {
  for (const path of ["results", "verification"]) {
    await page.goto(`/trips/${TRIP_ID}/${path}`);
    await expect(page.getByRole("heading", { name: "실제 연결에서는 검증 단계가 따로 없어요" })).toBeVisible();
    await expect(page.getByText("조정한 일정")).toHaveCount(0);
    await expect(page.getByRole("link", { name: "여행 화면으로" })).toHaveAttribute("href", `/trips/${TRIP_ID}`);
  }
});

test("선택·알림을 읽지 못해도(서버 500) 여행 화면은 그대로 뜨고, 읽지 못했다고 알린다", async ({ page, request }) => {
  await mockServer(request).scenario({ fail: "proposals" });
  await openTrip(page);
  await expect(page.getByRole("alert").filter({ hasText: "선택과 알림을 읽지 못했어요" })).toBeVisible();
  await expect(page.locator("#trip-pane-schedule").getByText("경복궁 관람")).toBeVisible();
  await expect(page.getByRole("heading", { name: "살펴볼 점" })).toBeVisible();     // 다른 패널은 영향받지 않는다
});

test("없는 여행 주소는 빈 화면이 아니라 이유와 다시 시도 단추를 보인다", async ({ page, request }) => {
  await mockServer(request).scenario({ trip: "missing" });
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(page.getByRole("button", { name: "다시 불러오기" })).toBeVisible();
  await expect(page.locator("main")).not.toBeEmpty();
});

test("서버에 연결이 안 되면 그 사실을 말하고, 화면은 비지 않는다", async ({ page }) => {
  await page.route("**/v1/web/**", (route) => route.abort());
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(page.getByText("서버에 연결하지 못했어요")).toBeVisible();
  await expect(page.getByRole("button", { name: "다시 불러오기" })).toBeVisible();
});

test("주요 화면을 여는 동안 브라우저 콘솔에 오류가 하나도 없다(없는 리소스·예외)", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ proposals: "open" });
  const problems: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") problems.push(`console: ${message.text()}`); });
  page.on("pageerror", (error) => problems.push(`exception: ${error.message}`));
  page.on("response", (response) => { if (response.status() >= 400 && !response.url().includes("/v1/web/")) problems.push(`${response.status()} ${response.url()}`); });

  for (const path of ["/", "/start", "/trips/new", `/trips/${TRIP_ID}`, `/trips/${TRIP_ID}/results`]) {
    await page.goto(path, { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
  }
  expect(problems).toEqual([]);
});

test("여행 화면을 열면 채팅 모델 예열을 서버에 한 번 청하고(사용자 키로), 키가 없는 첫 화면에서는 청하지 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page);
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(page.getByRole("heading", { name: "나의 여행", exact: true })).toBeVisible();
  await expect.poll(async () => (await server.received("POST", "/v1/web/warmup")).length).toBe(1);
  expect((await server.received("POST", "/v1/web/warmup"))[0].key).toBe("acop_u_known");

  await server.reset();
  const fresh = await page.context().browser()!.newContext();
  const other = await fresh.newPage();
  await other.goto("http://127.0.0.1:3102/");
  await other.waitForTimeout(1500);
  expect(await server.received("POST", "/v1/web/warmup")).toHaveLength(0);
  await fresh.close();
});
