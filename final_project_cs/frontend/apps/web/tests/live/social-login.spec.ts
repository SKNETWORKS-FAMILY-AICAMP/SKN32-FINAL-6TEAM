import { expect, test, type Page } from "@playwright/test";
import { agree, KEY_STORAGE, mockServer, SESSION_COOKIE, start, STUB } from "./helpers";

// `[2026-10-03 사용자 지시]` Social sign-in (`wiki/records/plans/2026-10-03_1930_소셜_로그인_백엔드_요청.md`): the card on My page, the menu
// row, and the page the provider sends the browser back to (`/auth/done`). The mock server plays the server AND the provider's page.

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const card = (page: Page) => page.getByRole("group", { name: "소셜 계정" });
// ★`[2026-10-05]` Google's row is Google's own button (no name next to it), so a row is found by the provider it belongs to.
const PROVIDER_ID: Record<string, string> = { 구글: "google", 카카오: "kakao", 네이버: "naver", 디스코드: "discord" };
const row = (page: Page, name: string) => card(page).locator(`li[data-provider="${PROVIDER_ID[name]}"]`);
/** The value of the session cookie this browser holds for the mock server (null = none). ★The page itself cannot read it (HttpOnly) — the browser context can. */
const cookie = async (page: Page) => (await page.context().cookies(STUB)).find((entry) => entry.name === SESSION_COOKIE)?.value ?? null;
/** No key is kept in the browser's storage any more. */
const storedKey = (page: Page) => page.evaluate((storage) => localStorage.getItem(storage), KEY_STORAGE);

test("서버에 소셜 로그인이 없으면(404) 「서버가 준비 중」이라고만 말하고 누를 단추도 메뉴 줄도 없다", async ({ page, request }) => {
  await mockServer(request).scenario({ social: "off" });
  await start(page);
  await page.goto("/mypage/account");
  await expect(card(page)).toContainText("서버가 준비 중이에요");
  await expect(card(page).getByRole("button")).toHaveCount(0);
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "메뉴" }).getByRole("link", { name: /계정 연결/ })).toHaveCount(0);
});

test("서버에 설정된 로그인 방법이 하나도 없으면(빈 목록) 그렇다고 말하고 단추를 두지 않는다", async ({ page, request }) => {
  await mockServer(request).scenario({ social: "none" });
  await start(page);
  await page.goto("/mypage/account");
  await expect(card(page)).toContainText("설정된 로그인 방법이 아직 없어요");
  await expect(card(page).getByRole("button")).toHaveCount(0);
});

test("통합 인증: 게스트가 구글로 계속하면 회원 쿠키를 받고 현재 여행을 보관한다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page);
  await page.goto("/mypage/account");
  await expect(row(page, "구글")).toBeVisible();
  await row(page, "구글").getByRole("button", { name: "Google 계정으로 계속" }).click();
  await expect(page.getByRole("heading", { name: "구글 계정으로 로그인했어요" })).toBeVisible();
  // the ticket is not left in the address bar
  expect(new URL(page.url()).search).toBe("");
  const [started] = await server.received("POST", "/google/start");
  expect(started).toMatchObject({ session: "known-session", csrf: "csrf-known", key: null });   // a link belongs to this browser's session (cookie + CSRF token)
  expect(started.body).toMatchObject({ mode: "login" });
  const nonce = String(started.body?.client_nonce);
  expect(nonce).toMatch(/^[0-9a-f]{64}$/);
  const [exchanged] = await server.received("POST", "/auth/exchange");
  expect(exchanged.key).toBeNull();                                           // the exchange needs no key (and creates none)
  expect(exchanged.body).toMatchObject({ client_nonce: nonce, ticket: expect.any(String), session: "cookie" });
  expect(await storedKey(page)).toBeNull();                                   // no key is kept in the browser
  expect(await cookie(page)).toMatch(/^member-session-/);                    // 로그인은 새 회원 세션으로 교체한다
  await page.getByRole("link", { name: "계속하기" }).click();
  await expect(row(page, "구글").getByText("연결됨")).toBeVisible();
  // the same session is a member's now: its page says so
  await expect(page.getByRole("group", { name: "로그인 상태" })).toContainText("로그인한 계정으로 쓰고 있어요");
  await expect(row(page, "카카오").getByRole("button", { name: "Kakao 계정으로 계속" })).toBeVisible();
});

test("구글 줄은 구글이 주는 공식 버튼 모양이다 — 흰 바탕·테두리·표준 색 G(네 색)·허용된 문구, 우리가 다시 칠하지 않고, 모든 업체에 공식 아이콘과 회사 이름을 표시한다", async ({ page, request }) => {
  await mockServer(request);
  await start(page);
  await page.goto("/mypage/account");
  const google = row(page, "구글").getByRole("button", { name: "Google 계정으로 계속" });
  await expect(google).toBeVisible();
  await expect(google).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(google).toHaveCSS("border-top-color", "rgb(116, 119, 117)");                  // 구글 규정 테두리 #747775
  await expect(google).toHaveCSS("border-top-width", "1px");
  await expect(google).toHaveCSS("height", "48px");
  const fills = await google.locator("svg path").evaluateAll((paths) => paths.map((path) => path.getAttribute("fill")));
  expect(fills).toEqual(["#EA4335", "#4285F4", "#FBBC05", "#34A853", "none"]);              // 표준 색 G, 흑백 아님
  const logo = (await google.locator("svg").boundingBox())!;
  expect(Math.round(logo.width)).toBe(Math.round(logo.height));                             // 가로세로 비율 그대로(늘리지 않음)
  await expect(row(page, "구글")).toHaveCount(1);
  await expect(row(page, "카카오").getByRole("button", { name: "Kakao 계정으로 계속" })).toBeVisible();  // 업체 이름과 공식 아이콘을 함께 표시
});

test("로그인: 세션이 없는 브라우저는 「구글 로그인」으로 그 계정의 세션 쿠키를 받고, 마이페이지에서 로그인한 계정이라고 보인다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page, null);
  await agree(page);                                                       // 약관에는 이미 동의한 사람 - 이 시험의 주제는 로그인이다
  await page.goto("/mypage/account");
  await expect(card(page)).not.toContainText("연결하기");                         // nothing to link without a session
  await row(page, "구글").getByRole("button", { name: "Google 계정으로 계속" }).click();
  await expect(page.getByRole("heading", { name: "구글 계정으로 로그인했어요" })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "여행 2개" })).toBeVisible();
  const [started] = await server.received("POST", "/google/start");
  expect(started).toMatchObject({ key: null, session: null });                // asking to sign in creates no user
  expect(started.body).toMatchObject({ mode: "login" });
  const [exchanged] = await server.received("POST", "/auth/exchange");
  expect(exchanged.body).toMatchObject({ session: "cookie" });                // a cookie session is asked for, never a key
  expect(await storedKey(page)).toBeNull();
  expect(await cookie(page)).toMatch(/^member-session-/);
  await page.getByRole("link", { name: "설정", exact: true }).click();
  // `[2026-10-13]` 설정 화면(/mypage)은 상태 줄 — 「로그인 상태」 카드는 「로그인 · 계정」 화면에 있다.
  await expect(page.getByRole("navigation", { name: "내 상태" }).getByRole("link", { name: /^로그인 · 계정/ })).toContainText("로그인됨");
  await page.goto("/mypage/account");
  await expect(page.getByRole("group", { name: "로그인 상태" })).toContainText("로그인한 계정으로 쓰고 있어요");
  await expect(page.getByText("내 여행 열쇠를 따로 보관해 주세요")).toHaveCount(0);
});

test("게스트는 자료 소실 경고 없이 한 버튼으로 계정을 선택한다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page);
  await page.goto("/mypage/account");
  await expect(card(page)).not.toContainText("게스트 여행은 사라지고");
  await expect(row(page, "구글").getByRole("button", { name: "Google 계정으로 계속" })).toHaveCount(1);
  await row(page, "카카오").getByRole("button", { name: "Kakao 계정으로 계속" }).click();
  await expect(page.getByRole("heading", { name: "카카오 계정으로 로그인했어요" })).toBeVisible();
  const [exchanged] = await server.received("POST", "/auth/exchange");
  expect(exchanged.session).toBe("known-session");
  expect(await cookie(page)).toMatch(/^member-session-/);
});

test("업체 화면에서 취소하면 「취소했어요」, 이미 다른 여행 기록에 붙은 계정이면 그 사정을 말하고 세션은 그대로다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page);
  await server.scenario({ socialResult: "cancelled" });
  await page.goto("/mypage/account");
  await row(page, "구글").getByRole("button", { name: "Google 계정으로 계속" }).click();
  await expect(page.getByRole("heading", { name: "로그인하지 못했어요" })).toBeVisible();
  await expect(page.locator("main").getByRole("alert")).toContainText("로그인을 취소했어요");
  expect((await server.received("POST", "/auth/exchange")).length).toBe(0);

  await server.scenario({ socialResult: "elsewhere", sessionKind: "member" });
  await page.goto("/mypage/account");
  await row(page, "구글").getByRole("button", { name: "Google 계정으로 계속" }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("이미 다른 여행 기록에 연결돼 있어요");
  expect(await cookie(page)).toBe("known-session");
});

test("이 브라우저가 시작하지 않은 로그인 링크(남이 보낸 ticket)는 서버에 묻지 않고 거절하며 세션을 바꾸지 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page);
  await page.goto("/auth/done?ticket=ticket-1");
  await expect(page.locator("main").getByRole("alert")).toContainText("이 브라우저에서 시작한 것이 아니에요");
  expect(new URL(page.url()).search).toBe("");
  expect((await server.received("POST", "/auth/exchange")).length).toBe(0);
  expect(await cookie(page)).toBe("known-session");
});

test("같은 ticket 을 두 번 쓰거나 다른 nonce 로 쓰면 서버가 거절하고(410), 화면은 처음부터 다시 하라고 한다", async ({ page }) => {
  await start(page);
  await page.goto("/mypage/account");
  await row(page, "구글").getByRole("button", { name: "Google 계정으로 계속" }).click();
  await expect(page.getByRole("heading", { name: "구글 계정으로 로그인했어요" })).toBeVisible();
  // the same ticket again, with a nonce this browser no longer holds
  await page.evaluate(() => sessionStorage.setItem("tripilot.web.auth.flow.v1", JSON.stringify({ provider: "google", mode: "link", nonce: "a".repeat(64), returnTo: "/mypage" })));
  await page.goto("/auth/done?ticket=ticket-1");
  await expect(page.locator("main").getByRole("alert")).toContainText("만료됐거나 이 브라우저에서 시작한 것이 아니에요");
});

test("연결 풀기: 「풀기」 → 「연결 풀기」 두 번 눌러야 풀리고, 여행은 그대로라고 말한다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page);
  await page.goto("/mypage/account");
  await row(page, "구글").getByRole("button", { name: "Google 계정으로 계속" }).click();
  await expect(page.getByRole("heading", { name: "구글 계정으로 로그인했어요" })).toBeVisible();
  await page.getByRole("link", { name: "계속하기" }).click();
  await row(page, "구글").getByRole("button", { name: "풀기" }).click();
  expect((await server.received("DELETE", "/auth/google")).length).toBe(0);   // the first press only asks
  await row(page, "구글").getByRole("button", { name: "연결 풀기" }).click();
  await expect(card(page).getByRole("status")).toContainText("구글 계정 연결을 풀었어요");
  await expect(row(page, "구글").getByRole("button", { name: "Google 계정으로 계속" })).toBeVisible();
  expect((await server.received("DELETE", "/auth/google")).length).toBe(1);
});

// `[2026-10-13 사용자 결정]` 전의 「계정 연결 · 로그인」 줄 대신, 게스트에게는 메뉴 프로필 칸의 단추가 「로그인 · 가입」이다(그 전 같은 날의 「계정으로 계속하기」를 바꿨다).
test("게스트의 메뉴 프로필 칸에는 「로그인 · 가입」이 있고, 누르면 돌아올 곳을 싣고 로그인 · 계정 화면으로 간다", async ({ page }) => {
  await start(page);
  await page.goto("/trips");
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  const menu = page.getByRole("dialog", { name: "메뉴" });
  await expect(menu.getByRole("button", { name: "로그아웃" })).toHaveCount(0);
  await menu.getByRole("link", { name: "로그인 · 가입", exact: true }).click();
  await expect(page).toHaveURL(/\/mypage\/account\?returnTo=%2Ftrips$/);
  await expect(menu).toHaveCount(0);                                         // 메뉴는 닫힌다
  await expect(card(page)).toBeVisible();
});

test("회원의 메뉴 프로필 칸에는 입구 대신 「프로필 수정」이 있고, 로그아웃은 메뉴에 없다(설정 › 로그인 · 계정 화면에만)", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ sessionKind: "member" });
  await start(page);
  await page.goto("/trips");
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  const menu = page.getByRole("dialog", { name: "메뉴" });
  await expect(menu.getByRole("link", { name: "로그인 · 가입", exact: true })).toHaveCount(0);
  await expect(menu.getByRole("link", { name: "프로필 수정", exact: true })).toBeVisible();
  await expect(menu.getByRole("button", { name: "로그아웃" })).toHaveCount(0);       // 로그아웃 자체는 session.spec 이 본다
  expect(await server.received("POST", "/v1/web/auth/logout")).toHaveLength(0);
});

test("세션 없는 로그인에 서버가 사람 확인을 요구했는데 확인 화면이 꺼져 있으면 서버 문장을 그대로 보인다", async ({ page, request }) => {
  await mockServer(request).scenario({ socialHumanCheck: "required" });
  await start(page, null);
  await agree(page);                                                       // 약관에는 이미 동의한 사람 - 이 시험의 주제는 로그인이다
  await page.goto("/mypage/account");
  await row(page, "구글").getByRole("button", { name: "Google 계정으로 계속" }).click();
  await expect(card(page).getByRole("alert")).toContainText("사람인지 확인해 주세요");
});
