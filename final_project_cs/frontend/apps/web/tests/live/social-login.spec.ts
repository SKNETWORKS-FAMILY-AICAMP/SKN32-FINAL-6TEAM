import { expect, test, type Page } from "@playwright/test";
import { KEY_STORAGE, mockServer, start } from "./helpers";

// `[2026-10-03 사용자 지시]` Social sign-in (`wiki/records/plans/2026-10-03_1930_소셜_로그인_백엔드_요청.md`): the card on My page, the menu
// row, and the page the provider sends the browser back to (`/auth/done`). The mock server plays the server AND the provider's page.

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const card = (page: Page) => page.getByRole("group", { name: "소셜 계정" });
const row = (page: Page, name: string) => card(page).getByRole("listitem").filter({ hasText: name });
const storedKey = (page: Page) => page.evaluate((storage) => localStorage.getItem(storage), KEY_STORAGE);

test("서버에 소셜 로그인이 없으면(404) 「서버가 준비 중」이라고만 말하고 누를 단추도 메뉴 줄도 없다", async ({ page, request }) => {
  await mockServer(request).scenario({ social: "off" });
  await start(page);
  await page.goto("/mypage");
  await expect(card(page)).toContainText("서버가 준비 중이에요");
  await expect(card(page).getByRole("button")).toHaveCount(0);
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "메뉴" }).getByRole("link", { name: /계정 연결/ })).toHaveCount(0);
});

test("서버에 설정된 로그인 방법이 하나도 없으면(빈 목록) 그렇다고 말하고 단추를 두지 않는다", async ({ page, request }) => {
  await mockServer(request).scenario({ social: "none" });
  await start(page);
  await page.goto("/mypage");
  await expect(card(page)).toContainText("설정된 로그인 방법이 아직 없어요");
  await expect(card(page).getByRole("button")).toHaveCount(0);
});

test("연결: 키가 있는 브라우저에서 「구글 연결하기」를 누르면 업체 화면을 거쳐 돌아와 「연결했어요」를 말하고, 마이페이지에 「연결됨」이 뜬다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page);
  await page.goto("/mypage");
  await expect(row(page, "구글")).toBeVisible();
  await row(page, "구글").getByRole("button", { name: "연결하기" }).click();
  await expect(page.getByRole("heading", { name: "구글 계정을 연결했어요" })).toBeVisible();
  // the ticket is not left in the address bar
  expect(new URL(page.url()).search).toBe("");
  const [started] = await server.received("POST", "/google/start");
  expect(started.key).toBe("acop_u_known");                                   // a link belongs to this browser's key
  expect(started.body).toMatchObject({ mode: "link" });
  const nonce = String(started.body?.client_nonce);
  expect(nonce).toMatch(/^[0-9a-f]{64}$/);
  const [exchanged] = await server.received("POST", "/auth/exchange");
  expect(exchanged.key).toBeNull();                                           // the exchange needs no key (and creates none)
  expect(exchanged.body).toMatchObject({ client_nonce: nonce, ticket: expect.any(String) });
  expect(await storedKey(page)).toBe("acop_u_known");                         // a link never changes the key
  await page.getByRole("link", { name: "계속하기" }).click();
  await expect(row(page, "구글").getByText("연결됨")).toBeVisible();
  await expect(row(page, "카카오").getByRole("button", { name: "연결하기" })).toBeVisible();
});

test("로그인: 키가 없는 브라우저는 「구글 로그인」으로 그 계정의 토큰을 받아 저장하고, 마이페이지에서 보관 안내를 본다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page, null);
  await page.goto("/mypage");
  await expect(card(page)).not.toContainText("연결하기");                         // nothing to link without a key
  await row(page, "구글").getByRole("button", { name: "로그인" }).click();
  await expect(page.getByRole("heading", { name: "구글 계정으로 로그인했어요" })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "여행 2개" })).toBeVisible();
  expect(await storedKey(page)).toBe("acop_u_social_account");
  const [started] = await server.received("POST", "/google/start");
  expect(started.key).toBeNull();                                             // asking to sign in creates no user
  expect(started.body).toMatchObject({ mode: "login" });
  await page.getByRole("link", { name: "마이페이지" }).click();
  await expect(page.getByRole("heading", { name: "내 여행 열쇠를 따로 보관해 주세요" })).toBeVisible();
});

test("이미 키가 있는 브라우저의 「로그인」은 키가 바뀐다는 경고를 먼저 보이고, 「연결하기」를 쓰라고 한다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page);
  await page.goto("/mypage");
  await expect(row(page, "구글")).toBeVisible();
  // no sign-in button until the warning is open
  await expect(row(page, "구글").getByRole("button", { name: "로그인" })).toHaveCount(0);
  await card(page).getByRole("button", { name: "계정으로 로그인하기" }).click();
  await expect(card(page).getByRole("alert").filter({ hasText: "토큰이 계정의 토큰으로 바뀌어요" })).toBeVisible();
  expect((await server.received("POST", "/start")).length).toBe(0);           // nothing was asked of the server yet
  await row(page, "카카오").getByRole("button", { name: "로그인" }).click();
  await expect(page.getByRole("heading", { name: "카카오 계정으로 로그인했어요" })).toBeVisible();
  expect(await storedKey(page)).toBe("acop_u_social_account");
});

test("업체 화면에서 취소하면 「취소했어요」, 이미 다른 토큰에 붙은 계정이면 그 사정을 말하고 키는 그대로다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page);
  await server.scenario({ socialResult: "cancelled" });
  await page.goto("/mypage");
  await row(page, "구글").getByRole("button", { name: "연결하기" }).click();
  await expect(page.getByRole("heading", { name: "로그인하지 못했어요" })).toBeVisible();
  await expect(page.locator("main").getByRole("alert")).toContainText("로그인을 취소했어요");
  expect((await server.received("POST", "/auth/exchange")).length).toBe(0);

  await server.scenario({ socialResult: "elsewhere" });
  await page.goto("/mypage");
  await row(page, "구글").getByRole("button", { name: "연결하기" }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("이미 다른 토큰에 연결돼 있어요");
  expect(await storedKey(page)).toBe("acop_u_known");
});

test("이 브라우저가 시작하지 않은 로그인 링크(남이 보낸 ticket)는 서버에 묻지 않고 거절하며 키를 바꾸지 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page);
  await page.goto("/auth/done?ticket=ticket-1");
  await expect(page.locator("main").getByRole("alert")).toContainText("이 브라우저에서 시작한 것이 아니에요");
  expect(new URL(page.url()).search).toBe("");
  expect((await server.received("POST", "/auth/exchange")).length).toBe(0);
  expect(await storedKey(page)).toBe("acop_u_known");
});

test("같은 ticket 을 두 번 쓰거나 다른 nonce 로 쓰면 서버가 거절하고(410), 화면은 처음부터 다시 하라고 한다", async ({ page, request }) => {
  await start(page);
  await page.goto("/mypage");
  await row(page, "구글").getByRole("button", { name: "연결하기" }).click();
  await expect(page.getByRole("heading", { name: "구글 계정을 연결했어요" })).toBeVisible();
  // the same ticket again, with a nonce this browser no longer holds
  await page.evaluate(() => sessionStorage.setItem("tripilot.web.auth.flow.v1", JSON.stringify({ provider: "google", mode: "link", nonce: "a".repeat(64), returnTo: "/mypage" })));
  await page.goto("/auth/done?ticket=ticket-1");
  await expect(page.locator("main").getByRole("alert")).toContainText("만료됐거나 이 브라우저에서 시작한 것이 아니에요");
});

test("연결 풀기: 「풀기」 → 「연결 풀기」 두 번 눌러야 풀리고, 토큰과 여행은 그대로라고 말한다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page);
  await page.goto("/mypage");
  await row(page, "구글").getByRole("button", { name: "연결하기" }).click();
  await expect(page.getByRole("heading", { name: "구글 계정을 연결했어요" })).toBeVisible();
  await page.getByRole("link", { name: "계속하기" }).click();
  await row(page, "구글").getByRole("button", { name: "풀기" }).click();
  expect((await server.received("DELETE", "/auth/google")).length).toBe(0);   // the first press only asks
  await row(page, "구글").getByRole("button", { name: "연결 풀기" }).click();
  await expect(card(page).getByRole("status")).toContainText("구글 계정 연결을 풀었어요");
  await expect(row(page, "구글").getByRole("button", { name: "연결하기" })).toBeVisible();
  expect((await server.received("DELETE", "/auth/google")).length).toBe(1);
});

test("메뉴에 「계정 연결 · 로그인」 줄이 있고 누르면 마이페이지의 소셜 계정 카드로 간다", async ({ page }) => {
  await start(page);
  await page.goto("/trips");
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await page.getByRole("dialog", { name: "메뉴" }).getByRole("link", { name: /계정 연결 · 로그인/ }).click();
  await expect(page).toHaveURL(/\/mypage#accounts$/);
  await expect(card(page)).toBeVisible();
});

test("키 없는 로그인에 서버가 사람 확인을 요구했는데 확인 화면이 꺼져 있으면 서버 문장을 그대로 보인다", async ({ page, request }) => {
  await mockServer(request).scenario({ socialHumanCheck: "required" });
  await start(page, null);
  await page.goto("/mypage");
  await row(page, "구글").getByRole("button", { name: "로그인" }).click();
  await expect(card(page).getByRole("alert")).toContainText("사람인지 확인해 주세요");
});
