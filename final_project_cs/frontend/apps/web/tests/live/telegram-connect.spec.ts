import { expect, test, type APIRequestContext, type Locator, type Page } from "@playwright/test";
import { agree, mockServer, start } from "./helpers";

/**
 * `[2026-10-05 사용자 지시]` 마이페이지 「텔레그램으로 연결」(알림만) — 버튼을 누르면 텔레그램 링크가 열리고, 텔레그램에서 「시작」을 누르면 서버가 대화를 묶는다.
 * mock 서버 시험(화면 반응) — 실서버 확인(서버 응답)은 따로 한다. 여기서 「시작」을 누르는 일은 mock 서버의 `/__test/telegram-open` 을 여는 것으로 흉내 낸다 —
 * 실제 텔레그램 봇이 서버에 업데이트를 넘기고 서버가 대화를 묶는 것은 이 시험이 보지 않는다.
 * 계약: `wiki/records/plans/2026-10-05_텔레그램_연결_백엔드_요청.md`.
 */
const WEBHOOK = "https://discord.com/api/web" + "hooks/123456789012345678/AbC-def_123456789012345";
const GUEST = "게스트는 일정 알림을 받지 않아요. 아래 소셜 계정을 연결하면 알림을 받을 수 있어요.";

test.beforeEach(async ({ page, request }) => {
  await mockServer(request).reset();
  await agree(page, { alert_channel: true });          // 알림 채널을 연결하려면 선택 동의(`alert_channel`)가 먼저다 - 이 시험들은 이미 동의한 고객이다
  await start(page);
});

/** 마이페이지의 한 줄: `<div><dt>제목</dt><dd>…</dd></div>`. */
const rowOf = (page: Page, title: string): Locator => page.locator("dl > div").filter({ has: page.locator("dt", { hasText: title }) });
const telegram = (page: Page) => rowOf(page, "텔레그램 알림");
const discord = (page: Page) => rowOf(page, "디스코드 웹훅");
const connectButton = (page: Page) => telegram(page).getByRole("button", { name: "텔레그램으로 연결", exact: true });
const openLink = (page: Page) => telegram(page).getByRole("link", { name: "텔레그램 열기" });
const connectedBadge = (page: Page) => telegram(page).getByText("연결됨", { exact: true });
const tag = (row: Locator) => row.getByText("알림을 받는 곳", { exact: true });

type Opened = { __opened: string[] };
/** 팝업이 막힌 브라우저: `window.open` 이 아무 창도 못 연다(시도한 주소만 센다). 눈에 보이는 링크 단추가 유일한 길이 된다. */
async function blockPopups(page: Page) {
  await page.addInitScript(() => {
    const seen: string[] = [];
    (window as unknown as Opened).__opened = seen;
    window.open = ((address?: string | URL) => { seen.push(String(address)); return null; }) as typeof window.open;
  });
}
const opened = (page: Page) => page.evaluate(() => (window as unknown as Opened).__opened);

/** 링크 단추를 눌러 새 탭을 연다 = 고객이 텔레그램에서 「시작」을 누른 것(mock 서버가 대화를 묶는다). */
async function tapStart(page: Page) {
  const [tab] = await Promise.all([page.context().waitForEvent("page"), openLink(page).click()]);
  await expect(tab.getByRole("heading", { name: "텔레그램 연결됨 (mock 서버)" })).toBeVisible();
  await tab.close();
}

/** 텔레그램 줄을 연 채로 연결까지 끝낸다(팝업은 막힌 상태). */
async function connected(page: Page, request: APIRequestContext, scene = "on") {
  await mockServer(request).scenario({ telegram: scene });
  await blockPopups(page);
  await page.goto("/mypage");
  await connectButton(page).click();
  await tapStart(page);
  await expect(connectedBadge(page)).toBeVisible();
}

test("서버가 텔레그램을 알리지 않으면(옛 서버) 텔레그램 줄이 통째로 없다", async ({ page, request }) => {
  const server = mockServer(request);
  await page.goto("/mypage");
  await expect(page.getByRole("link", { name: "웹훅 등록하기" })).toBeVisible();           // 프로필을 다 읽은 뒤의 화면이다
  await expect(telegram(page)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "텔레그램으로 연결" })).toHaveCount(0);
  expect(await server.received("POST", "/v1/web/profile/telegram/connect/start")).toHaveLength(0);
});

test("프로필 자체를 못 읽는 서버면 텔레그램 줄도 없다 - 단추를 그리지 않는다", async ({ page, request }) => {
  await mockServer(request).scenario({ telegram: "on", profile: "off" });
  await page.goto("/mypage");
  await expect(page.getByText("이 서버는 웹훅 저장을 지원하지 않아요.")).toBeVisible();
  await expect(telegram(page)).toHaveCount(0);
});

test("연결 단추를 누르면 눈에 보이는 링크 단추와 남은 시간이 뜨고, 텔레그램에서 「시작」을 누른 것이 서버에 닿으면 「연결됨」과 알림 받는 곳이 뜬다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ telegram: "on" });
  await blockPopups(page);
  await page.goto("/mypage");
  await expect(connectButton(page)).toBeVisible();
  await expect(telegram(page)).toContainText("텔레그램 앱이 열려요. 「시작」을 한 번 누르면 끝이에요.");
  await expect(telegram(page)).toContainText("텔레그램이 없으면 먼저 설치해 주세요(무료).");
  await expect(telegram(page)).toContainText("이 채팅은 알림 전용이라 답장은 받지 않아요.");

  await connectButton(page).click();
  await expect(openLink(page)).toBeVisible();                                                  // 팝업이 막혀도 이 단추가 있다
  await expect(openLink(page)).toHaveAttribute("target", "_blank");
  await expect(openLink(page)).toHaveAttribute("rel", /noopener/);
  await expect(openLink(page)).toHaveAttribute("href", /^http:\/\/127\.0\.0\.1:\d+\/__test\/telegram-open\?code=/);
  await expect(telegram(page)).toContainText(/텔레그램에서 「시작」을 눌러 주세요 · 남은 시간 (10:00|09:5\d)/);
  await expect(telegram(page).getByRole("button", { name: "취소" })).toBeVisible();
  await expect(connectButton(page)).toHaveCount(0);
  expect(await opened(page)).toHaveLength(1);                                                  // 창 열기를 시도는 했다(막혀도 괜찮다)
  const code = new URL((await openLink(page).getAttribute("href")) ?? "").searchParams.get("code") ?? "";
  expect(code).not.toBe("");

  await tapStart(page);
  await expect(connectedBadge(page)).toBeVisible();                                           // 2초마다 다시 읽다가 알아본다
  await expect(tag(telegram(page))).toBeVisible();
  await expect(telegram(page).getByRole("status").filter({ hasText: "텔레그램이 연결됐어요" })).toBeVisible();
  await expect(telegram(page).getByText("아직 시험 메시지를 보내지 않았어요.")).toBeVisible();
  await expect(telegram(page).getByRole("button", { name: "시험 메시지 보내기" })).toBeVisible();
  await expect(telegram(page).getByRole("button", { name: "연결 풀기" })).toBeVisible();
  await expect(openLink(page)).toHaveCount(0);

  expect(await server.received("POST", "/v1/web/profile/telegram/connect/start")).toHaveLength(1);
  expect(await server.received("GET", "/__test/telegram-open")).toHaveLength(1);
  expect((await server.received("GET", "/v1/web/profile")).length).toBeGreaterThan(1);       // 기다리는 동안 프로필을 다시 읽었다
  expect(await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }))).not.toContain(code);   // 일회용 코드는 이 브라우저에 남지 않는다
  expect(page.url()).not.toContain(code);
});

test("브라우저가 창을 열게 해 주면 링크를 따로 누르지 않아도 텔레그램이 열리고 연결된다", async ({ page, request }) => {
  await mockServer(request).scenario({ telegram: "on" });
  await page.goto("/mypage");
  const popup = page.context().waitForEvent("page");
  await connectButton(page).click();
  const tab = await popup;
  await expect(tab).toHaveURL(/\/__test\/telegram-open\?code=/);
  await expect(connectedBadge(page)).toBeVisible();
  await expect(tag(telegram(page))).toBeVisible();
});

test("대기 중 「취소」를 누르면 연결 단추로 돌아오고, 서버를 다시 읽는 일도 멈춘다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ telegram: "on" });
  await blockPopups(page);
  await page.goto("/mypage");
  await connectButton(page).click();
  await expect(openLink(page)).toBeVisible();
  await telegram(page).getByRole("button", { name: "취소" }).click();
  await expect(connectButton(page)).toBeEnabled();
  await expect(openLink(page)).toHaveCount(0);
  await expect(telegram(page).getByRole("alert")).toHaveCount(0);
  await page.waitForTimeout(500);                                                                // 취소 순간에 날아가던 요청이 끝나도록
  const before = (await server.received("GET", "/v1/web/profile")).length;
  await page.waitForTimeout(2500);                                                               // 읽는 간격(2초)보다 길게 기다려도 늘지 않는다
  expect((await server.received("GET", "/v1/web/profile")).length).toBe(before);
});

test("시험 메시지: 닿으면 그렇게 말한다", async ({ page, request }) => {
  const server = mockServer(request);
  await connected(page, request);
  await telegram(page).getByRole("button", { name: "시험 메시지 보내기" }).click();
  await expect(telegram(page).getByRole("status").filter({ hasText: "텔레그램 대화로 시험 메시지를 보냈어요." })).toBeVisible();
  await expect(telegram(page).getByText("시험 메시지가 도착했어요.")).toBeVisible();
  expect(await server.received("POST", "/v1/web/profile/telegram/test")).toHaveLength(1);
});

test("시험 메시지: 고객이 봇을 차단했으면 알림이 닿지 않는다고 말한다", async ({ page, request }) => {
  await connected(page, request, "blocked");
  await telegram(page).getByRole("button", { name: "시험 메시지 보내기" }).click();
  await expect(telegram(page).getByRole("status").filter({ hasText: "시험 메시지를 보내지 못했어요. 텔레그램에서 봇을 차단해 둔 것 같아요." })).toBeVisible();
  await expect(telegram(page).getByText("텔레그램에서 봇을 차단해서 알림이 닿지 않아요. 차단을 풀고 시험 메시지를 다시 보내 보세요.")).toBeVisible();
  await expect(telegram(page).getByText("시험 메시지가 도착했어요.")).toHaveCount(0);
});

test("시험 메시지: 너무 자주 누르면 서버 문장을 그대로 보인다", async ({ page, request }) => {
  await connected(page, request, "too_soon");
  await telegram(page).getByRole("button", { name: "시험 메시지 보내기" }).click();
  await expect(telegram(page).getByRole("status").filter({ hasText: "20초 뒤에 다시 해 주세요" })).toBeVisible();
});

test("연결 풀기는 두 단계다 - 첫 누름은 확인만 묻고 서버를 부르지 않으며, 「정말 풀기」에서야 한 번 지운다", async ({ page, request }) => {
  const server = mockServer(request);
  await connected(page, request);
  const line = telegram(page);
  await line.getByRole("button", { name: "연결 풀기" }).click();
  await expect(line.getByRole("button", { name: "정말 풀기" })).toBeVisible();
  await expect(line.getByRole("button", { name: "취소" })).toBeVisible();
  expect(await server.received("DELETE", "/v1/web/profile/telegram")).toHaveLength(0);

  await line.getByRole("button", { name: "취소" }).click();                                      // 취소하면 그대로다
  await expect(line.getByRole("button", { name: "연결 풀기" })).toBeVisible();
  await expect(line.getByRole("button", { name: "정말 풀기" })).toHaveCount(0);
  expect(await server.received("DELETE", "/v1/web/profile/telegram")).toHaveLength(0);

  await line.getByRole("button", { name: "연결 풀기" }).click();
  await line.getByRole("button", { name: "정말 풀기" }).click();
  await expect(connectButton(page)).toBeVisible();                                              // 연결 안 된 모양으로 돌아온다
  await expect(connectedBadge(page)).toHaveCount(0);
  await expect(tag(line)).toHaveCount(0);
  expect(await server.received("DELETE", "/v1/web/profile/telegram")).toHaveLength(1);
});

test("연결 시작이 실패하면 서버 문장을 보이고 텔레그램 창도 링크 단추도 만들지 않는다", async ({ page, request }) => {
  await mockServer(request).scenario({ telegram: "start_fails" });
  await blockPopups(page);
  await page.goto("/mypage");
  await connectButton(page).click();
  await expect(telegram(page).getByRole("alert").filter({ hasText: "텔레그램 연결을 시작하지 못했어요" })).toBeVisible();
  await expect(openLink(page)).toHaveCount(0);
  await expect(connectButton(page)).toBeEnabled();
  expect(await opened(page)).toHaveLength(0);
});

test("서버가 텔레그램 것이 아닌 주소를 주면 따라가지 않는다", async ({ page, request }) => {
  await mockServer(request).scenario({ telegram: "bad_link" });
  await blockPopups(page);
  await page.goto("/mypage");
  await connectButton(page).click();
  await expect(telegram(page).getByRole("alert").filter({ hasText: "서버가 텔레그램 연결 주소를 주지 않았어요." })).toBeVisible();
  await expect(openLink(page)).toHaveCount(0);
  await expect(connectButton(page)).toBeEnabled();
  expect(await opened(page)).toHaveLength(0);                                                   // 낯선 주소로는 창도 열지 않았다
});

test("연결 시간이 지나면 그렇게 말하고 단추가 돌아오며, 다시 누르면 새 링크로 연결된다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ telegram: "short" });                                                 // 시작 뒤 2초면 코드가 끝난다
  await blockPopups(page);
  await page.goto("/mypage");
  await connectButton(page).click();
  await expect(telegram(page).getByRole("alert").filter({ hasText: "연결 시간이 지났어요. 다시 눌러 주세요." })).toBeVisible();
  await expect(openLink(page)).toHaveCount(0);
  await expect(connectButton(page)).toBeEnabled();
  await expect(connectedBadge(page)).toHaveCount(0);

  await server.scenario({ telegram: "on" });
  await connectButton(page).click();
  await expect(telegram(page).getByRole("alert")).toHaveCount(0);                              // 지난 시간 문구는 새로 누르면 사라진다
  await tapStart(page);
  await expect(connectedBadge(page)).toBeVisible();
  expect(await server.received("POST", "/v1/web/profile/telegram/connect/start")).toHaveLength(2);
});

test("디스코드 웹훅도 있으면 알림은 한 곳으로만 간다 - 마지막에 연결한 곳이 받고, 「이 채널로 받기」로 바꾼다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ telegram: "on" });
  await blockPopups(page);
  await page.goto("/mypage/edit");                                                              // 디스코드 웹훅을 먼저 저장한다
  await page.getByRole("textbox", { name: "디스코드 웹훅 URL (선택)" }).fill(WEBHOOK);
  await page.getByRole("button", { name: "저장" }).click();
  await expect(page).toHaveURL(/\/mypage$/);
  const hook = discord(page), line = telegram(page);
  await expect(tag(hook)).toBeVisible();
  await expect(hook.getByRole("button", { name: "이 채널로 받기" })).toHaveCount(0);
  await expect(connectButton(page)).toBeVisible();

  await connectButton(page).click();                                                            // 텔레그램을 나중에 연결 → 알림은 텔레그램으로
  await tapStart(page);
  await expect(tag(line)).toBeVisible();
  await expect(line.getByRole("button", { name: "이 채널로 받기" })).toHaveCount(0);
  await expect(tag(hook)).toHaveCount(0);
  await expect(hook.getByRole("button", { name: "이 채널로 받기" })).toBeVisible();

  await hook.getByRole("button", { name: "이 채널로 받기" }).click();                            // 디스코드로 되돌린다
  await expect(tag(hook)).toBeVisible();
  await expect(hook.getByRole("button", { name: "이 채널로 받기" })).toHaveCount(0);
  await expect(tag(line)).toHaveCount(0);
  await expect(line.getByRole("button", { name: "이 채널로 받기" })).toBeVisible();

  await line.getByRole("button", { name: "이 채널로 받기" }).click();                            // 다시 텔레그램으로
  await expect(tag(line)).toBeVisible();
  await expect(tag(hook)).toHaveCount(0);
  expect((await server.received("PUT", "/v1/web/profile")).map((entry) => entry.body))
    .toEqual([{ discord_webhook_url: WEBHOOK }, { notice_channel: "discord" }, { notice_channel: "telegram" }]);
});

test("옛 서버라서 텔레그램을 모르면 디스코드 줄에는 꼬리표도 「이 채널로 받기」도 생기지 않는다", async ({ page, request }) => {
  await page.goto("/mypage/edit");
  await page.getByRole("textbox", { name: "디스코드 웹훅 URL (선택)" }).fill(WEBHOOK);
  await page.getByRole("button", { name: "저장" }).click();
  await expect(page).toHaveURL(/\/mypage$/);
  await expect(discord(page).getByRole("button", { name: "시험 메시지 보내기" })).toBeVisible();
  await expect(tag(discord(page))).toHaveCount(0);
  await expect(discord(page).getByRole("button", { name: "이 채널로 받기" })).toHaveCount(0);
  expect(await mockServer(request).received("PUT", "/v1/web/profile")).toHaveLength(1);
});

test("게스트에게는 줄 맨 아래에 일정 알림을 받지 않는다는 문장이 있고, 회원에게는 없다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ telegram: "on" });                                                    // 기본 세션 = 게스트
  await page.goto("/mypage");
  await expect(connectButton(page)).toBeVisible();
  await expect(telegram(page).getByText(GUEST)).toBeVisible();
  await expect(telegram(page).locator("dd > span").last()).toHaveText(GUEST);                   // 맨 아래

  await server.scenario({ sessionKind: "member" });
  await page.reload();
  await expect(connectButton(page)).toBeVisible();
  await expect(telegram(page).getByText("게스트는 일정 알림을 받지 않아요")).toHaveCount(0);
});
