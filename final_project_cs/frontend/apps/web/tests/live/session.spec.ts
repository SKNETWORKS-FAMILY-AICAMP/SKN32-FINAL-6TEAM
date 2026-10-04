import { expect, test } from "@playwright/test";
import { APP, KEY_STORAGE, KNOWN_SESSION, mockServer, SESSION_COOKIE, start, startWithOldKey, STUB, TRIP_ID } from "./helpers";

/**
 * `[2026-10-04 사용자 결정 · 서버 D-CS-011]` 브라우저는 키를 두지 않는다 — 서버가 HttpOnly 쿠키 세션을 주고, 쓰기에는 보안 토큰(X-CSRF-Token)이 따른다.
 * (이 파일은 옛 `keys.spec.ts`(토큰 보기·복사·교체)를 대신한다. 소셜 계정은 `social-login.spec.ts`.)
 * 목 서버 시험이다 — 화면이 무엇을 보내고 어떻게 반응하는지를 본다. 서버 응답 자체는 실서버 확인(`tests/real`)이 따로 본다.
 */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const paths = async (request: Parameters<typeof mockServer>[0]) => (await mockServer(request).log()).map((entry) => `${entry.method} ${entry.path}`);

test("내 여행이 있으면 첫 화면의 「내 여행」 카드에 뜨고 그 여행으로 간다", async ({ page }) => {
  await start(page);
  await page.goto("/");
  const card = page.getByRole("region", { name: "내 여행", exact: true });
  await expect(card).toBeVisible();
  await expect(card).toContainText("내 여행");
  await card.getByRole("link").click();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));
});

test("여행이 없으면 「아직 등록한 여행이 없어요」가 뜨고, 세션이 없으면 목록을 묻느라 새 사용자를 만들지도 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ trips: "none" });
  await start(page);
  await page.goto("/");
  await expect(page.getByRole("region", { name: "내 여행", exact: true })).toContainText("아직 등록한 여행이 없어요.");

  await server.reset();
  const fresh = await page.context().browser()!.newContext();
  const first = await fresh.newPage();
  await first.goto(`${APP}/`);
  await expect(first.getByRole("region", { name: /내 여행|My trips/, exact: false }).first()).toBeVisible();
  const log = await paths(request);
  expect(log).toContain("GET /v1/web/auth/me");                          // 누구인지만 묻는다
  expect(log).not.toContain("POST /v1/web/auth/session");               // 새 게스트를 만들지 않는다
  expect(log).not.toContain("GET /v1/web/trips");                        // 목록도 묻지 않는다(세션이 없으니 등록한 것이 없다)
  await fresh.close();
});

test("게스트의 마이페이지: 「로그인 상태」 칸이 사라지는 때와 제한을 말하고, 토큰은 보여 주지도 받지도 않는다", async ({ page }) => {
  await start(page);
  await page.goto("/mypage");
  const status = page.getByRole("group", { name: "로그인 상태" });
  await expect(status).toBeVisible();
  await expect(status).toContainText("게스트로 쓰고 있어요");
  await expect(status).toContainText("7일 동안 쓰지 않으면");                 // guest_idle_hours 168 → 7일
  await expect(status).toContainText("여행을 1개까지");
  await expect(status.getByRole("button", { name: "로그아웃" })).toHaveCount(0);   // 게스트는 로그아웃할 것이 없다
  // 토큰 화면은 없다
  await expect(page.getByText("발급된 토큰")).toHaveCount(0);
  await expect(page.getByRole("group", { name: "토큰 관리" })).toHaveCount(0);
  await expect(page.getByText("내 여행 열쇠를 따로 보관해 주세요")).toHaveCount(0);
  await expect(page.locator("#main-content").getByText("게스트", { exact: true })).toBeVisible();
});

test("회원의 마이페이지: 로그아웃하면 보안 토큰과 함께 서버에 알리고, 그 뒤로는 세션이 없는 모습이 된다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ sessionKind: "member" });
  await start(page);
  await page.goto("/mypage");
  const status = page.getByRole("group", { name: "로그인 상태" });
  await expect(status).toContainText("로그인한 계정으로 쓰고 있어요");
  await status.getByRole("button", { name: "로그아웃" }).click();
  await expect(status.getByRole("status")).toContainText("로그아웃했어요");
  const [out] = await server.received("POST", "/v1/web/auth/logout");
  expect(out.csrf).toBe("csrf-known");                                    // 쓰기에는 보안 토큰이 따른다
  expect(out.session).toBe(KNOWN_SESSION);
  await expect(status).toContainText("아직 시작하지 않았어요");
  await page.goto("/");
  await expect(page.getByRole("region", { name: "내 여행", exact: true })).toContainText("아직 등록한 여행이 없어요.");
});

test("옛 키만 있는 브라우저: 처음 열 때 키 하나로 세션으로 옮겨지고(쿠키 없이), 키는 지워지고, 여행 목록이 그대로 열린다", async ({ page, request }) => {
  const server = mockServer(request);
  await startWithOldKey(page);
  await page.goto("/");
  // ★「내 여행」 머리글은 목록이 오기 전에도 있다 — 여행 링크가 보여야 키 이전과 목록 호출이 끝난 것이다(머리글만 보고 기록을 읽으면 앞선다).
  await expect(page.getByRole("region", { name: "내 여행", exact: true }).getByRole("link").first()).toBeVisible();
  const [adopt] = await server.received("POST", "/v1/web/auth/adopt");
  expect(adopt.key).toBe("acop_u_known");
  expect(adopt.session).toBeNull();                                       // ★키와 쿠키를 함께 보내지 않는다(서버는 400 ambiguous_credentials)
  expect(await server.received("POST", "/v1/web/auth/session")).toHaveLength(0);   // 새 사용자를 만들지 않고 같은 사용자를 옮겼다
  expect(await page.evaluate((key) => localStorage.getItem(key), KEY_STORAGE)).toBeNull();
  // 옮긴 뒤의 요청은 쿠키만 보낸다
  const trips = await server.received("GET", "/v1/web/trips");
  expect(trips.length).toBeGreaterThan(0);
  expect(trips.every((entry) => entry.key === null && entry.session !== null)).toBe(true);
});

test("서버가 모르는 세션(끝났거나 지워진 쿠키)이면 조용히 새 사용자가 되지 않는다: 목록은 비어 보이고, 여행을 직접 열면 어떻게 하면 되는지 알려 준다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page, "acop_u_expired");                                    // 서버가 모르는 쿠키
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(page.getByText(/마이페이지에서 로그인하면 다시 열려요/)).toBeVisible();
  expect(await server.received("POST", "/v1/web/auth/session")).toHaveLength(0);
  expect(await server.received("GET", `/v1/web/trips/${TRIP_ID}`)).toHaveLength(0);   // 여행을 묻지도 않았다
  // 서버는 모르는 쿠키를 지우라고 했다
  const cookies = await page.context().cookies(STUB);
  expect(cookies.find((cookie) => cookie.name === SESSION_COOKIE)).toBeUndefined();
});

test("쓰기가 보안 토큰 때문에 한 번 거절되면(403 csrf_failed) 토큰을 다시 받아 한 번 더 보내고, 사용자는 모른다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page);
  await page.goto("/trips");
  await server.scenario({ csrfRefuse: 1 });
  await page.locator("#main-content li").first().getByRole("button").click();
  await page.getByRole("alertdialog").getByRole("button", { name: "삭제", exact: true }).click();
  await expect.poll(async () => (await server.received("POST", `/v1/web/trips/${TRIP_ID}/delete`)).length).toBe(2);   // 거절된 것 + 다시 보낸 것
  const asks = await server.received("GET", "/v1/web/auth/me");
  expect(asks.length).toBeGreaterThanOrEqual(2);                          // 처음 + 토큰을 다시 받으려고
});

test("게스트의 제한에 걸리면(403 guest_trip_limit · login_required) 서버 문장 그대로 알리고, 계정을 연결하러 가는 길을 보인다 — 읽은 계획은 그대로다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ guestLimit: "trip_limit" });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill("10/1 09:00 경복궁 관람");
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);
  await page.getByRole("button", { name: "여행 등록" }).click();
  const alert = page.getByRole("alert").filter({ hasText: "게스트는 여행을 1개까지" });
  await expect(alert).toBeVisible();
  await expect(alert).toContainText("로그인하면 더 만들 수 있어요");            // 서버의 문장 그대로
  const way = alert.getByRole("link", { name: "마이페이지에서 계정을 연결하기" });
  await expect(way).toHaveAttribute("href", "/mypage#accounts");
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible();   // 읽은 계획은 그대로 보인다
  await way.click();
  await expect(page).toHaveURL(/\/mypage#accounts$/);
  await expect(page.getByRole("group", { name: "소셜 계정" })).toBeVisible();
  // 다른 제한(시작이 너무 멀다 · 너무 길다)도 같은 모양이다
  await server.scenario({ guestLimit: "too_far" });
  await page.goBack();
  await page.getByRole("button", { name: "여행 등록" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "1년 안에 시작하는 여행만" })).toBeVisible();
});

test("메뉴에는 토큰 화면이 없고 마이페이지로 가는 길만 있다", async ({ page }) => {
  await start(page);
  await page.goto("/");
  await page.getByRole("button", { name: "메뉴", exact: true }).first().click();
  const dialog = page.getByRole("dialog", { name: "메뉴" });
  await expect(dialog.getByRole("link", { name: /마이페이지/ })).toBeVisible();
  await expect(dialog.getByRole("group", { name: "토큰 관리" })).toHaveCount(0);
  await expect(dialog.getByRole("button", { name: /다시 발급받기/ })).toHaveCount(0);
});

test("내 여행 목록을 읽지 못해도(서버 500) 첫 화면은 그대로 쓸 수 있고, 못 읽었다고 알린다(여행이 없다는 말이 아니다)", async ({ page, request }) => {
  await mockServer(request).scenario({ fail: "trips" });
  await start(page);
  await page.goto("/");
  const card = page.getByRole("region", { name: "내 여행", exact: true });
  await expect(card.getByRole("alert")).toBeVisible();
  await expect(card.getByRole("button", { name: "다시 불러오기" })).toBeVisible();
  await expect(card).not.toContainText("아직 등록한 여행이 없어요");
});
