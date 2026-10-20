import { expect, test, type Page } from "@playwright/test";
import { agree, agreeTerms, beforeTheTrip, checkPlan, CONSENT_STORAGE, mockServer, openRegistration, start, startCardHead, TRIP_ID, tripScreen, useKorean } from "./helpers";

/**
 * `[2026-10-16 사용자 결정 — ST4F-601]` 로그인 먼저 · 약관 화면과 취향 설문 입구 나누기 · 뒤로가기 묶음.
 * - 약관이 필요한 화면은 `/start?terms=required&returnTo=…`(약관 카드만)으로 보내고, 동의하면 그 화면으로 돌아간다(약관 화면은 기록에 남지 않는다).
 * - `/start`(메뉴 「여행 취향 설문」)는 취향 설문 입구: 동의 전이면 약관 카드, 동의했으면 취향 카드를 스스로 연다. 디스코드 카드는 로그인한 회원에게만.
 * - 「로그인 · 가입」(`/mypage/account`)은 동의 없이 열린다. 설정 하위 화면의 「뒤로」는 온 길로, 로그아웃은 이 기기의 동의 사본과 취향 답도 지운다.
 * 테스트용 모방 서버로 도는 화면 시험이다(실제 서버 확인이 아니다).
 */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const ONBOARDING_STORAGE = "tripilot.web.onboarding.v2";
const DRAFT_STORAGE = "tripilot.web.registration-draft.v1";
const card = (page: Page, id: 0 | 1 | 2) => page.locator(`[data-card="${id}"]`);
const back = (page: Page) => page.getByRole("button", { name: "뒤로", exact: true });

async function openMenu(page: Page) {
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  return page.getByRole("dialog", { name: "메뉴" });
}

/** Menu › 설정 › 로그인 · 계정, moving inside the app. */
async function openAccountFromMenu(page: Page) {
  await (await openMenu(page)).getByRole("link", { name: /^설정/ }).click();
  await expect(page).toHaveURL(/\/mypage$/);
  await page.getByRole("navigation", { name: "내 상태" }).getByRole("link", { name: /^로그인 · 계정/ }).click();
  await expect(page).toHaveURL(/\/mypage\/account$/);
}

test("처음 온 사람(쿠키 · 동의 없음)이 메뉴의 「로그인 · 가입」을 누르면 약관 화면을 거치지 않고 바로 로그인 화면이 열린다", async ({ page }) => {
  await useKorean(page);
  await page.goto("/");
  await (await openMenu(page)).getByRole("link", { name: "로그인 · 가입", exact: true }).click();
  await expect(page).toHaveURL(/\/mypage\/account\?returnTo=%2F$/);
  await expect(page.getByRole("group", { name: "소셜 계정" }).getByRole("button", { name: "Google 계정으로 계속" })).toBeVisible();
  await expect(page).not.toHaveURL(/\/start/);                                          // 구글 단추가 보인 뒤에도 약관 화면으로 넘어가지 않았다
  await expect(page.getByText("이용을 위해서는 필수 약관 동의가 필요해요.")).toHaveCount(0);
});

test("약관이 필요한 화면은 약관 카드만 있는 약관 화면으로 보내고, 동의하면 그 화면으로 돌아오며, 브라우저 뒤로는 약관 화면에 닿지 않는다", async ({ page }) => {
  await useKorean(page);
  await page.goto("/");
  await page.goto("/mypage/consents");
  await expect(page).toHaveURL(/\/start\?terms=required&returnTo=%2Fmypage%2Fconsents$/);
  await expect(page).toHaveTitle("구구루트 · 약관 동의");
  await expect(page.getByRole("heading", { name: "약관 동의", level: 1 })).toBeVisible();
  await expect(page.getByText("동의하면 보던 화면으로 돌아가요.")).toBeVisible();
  await expect(card(page, 1)).toHaveCount(1);
  await expect(card(page, 0)).toHaveCount(0);                                           // 디스코드 카드 없음
  await expect(card(page, 2)).toHaveCount(0);                                           // 취향 카드 없음
  await expect(page.getByText(/정답은 없어요/)).toHaveCount(0);
  await expect(page.getByRole("status").filter({ hasText: "이용을 위해서는 필수 약관 동의가 필요해요." })).toBeVisible();
  await agreeTerms(page);                                                               // 「동의하고 다음으로」 → /mypage/consents 로 바뀐다(helpers 가 주소를 본다)
  await expect(page.getByRole("heading", { name: "약관 동의 관리" })).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(/\/$/);                                                  // 약관 화면이 아니라 그 앞의 소개 화면
  await expect(page).not.toHaveURL(/\/start/);
});

test("취향 설문 입구(/start)는 동의 전이면 약관 · 취향 카드만 두고(게스트에게 디스코드 카드 없음) 약관 카드를 스스로 열며, 동의하면 주소 그대로 취향 카드가 열린다", async ({ page, request }) => {
  const server = mockServer(request);
  await useKorean(page);
  await page.goto("/start");
  await expect(page).toHaveTitle("구구루트 · 여행 취향 설문");
  await expect(page.getByRole("heading", { name: "여행 취향 설문", level: 1 })).toBeVisible();
  await expect(page.getByText("설문을 하려면 먼저 약관에 동의해 주세요.")).toBeVisible();
  await expect(startCardHead(page, "terms")).toHaveAttribute("aria-expanded", "true");
  await expect(card(page, 1)).toHaveCount(1);
  await expect(card(page, 2)).toHaveCount(1);
  await expect(card(page, 0)).toHaveCount(0);
  await agreeTerms(page, ["alert_channel"]);                                            // 주소는 /start 그대로, 취향 카드가 열린다(helpers 가 본다)
  await expect(page.getByRole("heading", { name: "여행 취향 설문을 시작할게요", exact: true })).toBeVisible();
  await expect(page.getByText("4가지 질문에 답해 주세요. 나중에 다시 고칠 수 있어요.")).toBeVisible();
  expect(await server.received("PUT", "/v1/web/profile")).toHaveLength(0);              // 알림 채널에 동의해도 게스트는 웹훅을 보내지 않는다
});

test("디스코드 알림 카드는 회원 세션에만 보인다 — 같은 브라우저라도 게스트 세션이면 없다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page);                                                                    // 게스트 세션 · 동의함
  await page.goto("/start");
  await expect(startCardHead(page, "preferences")).toHaveAttribute("aria-expanded", "true");   // 동의했으면 취향 카드를 스스로 연다
  await expect(card(page, 2)).toHaveCount(1);
  await expect(card(page, 0)).toHaveCount(0);
  await server.scenario({ sessionKind: "member" });
  await page.reload();
  await expect(card(page, 0)).toHaveCount(1);
  await expect(page.getByRole("button", { name: /디스코드 알림/ })).toContainText("선택");
});

test("「뒤로」는 온 길로 간다: 소개 → 메뉴 「로그인 · 가입」 → 뒤로는 소개, 여행 목록 → 설정 → 로그인 · 계정 → 뒤로 → 뒤로는 설정 · 여행 목록, 바로 연 하위 화면의 뒤로는 설정", async ({ page }) => {
  await useKorean(page);
  await page.goto("/");
  await (await openMenu(page)).getByRole("link", { name: "로그인 · 가입", exact: true }).click();
  await expect(page).toHaveURL(/\/mypage\/account\?returnTo=%2F$/);
  await back(page).click();
  await expect(page).toHaveURL(/\/$/);

  await agree(page);                                                                    // 다음 읽기부터 동의한 방문자
  await page.goto("/trips");
  await openAccountFromMenu(page);
  await back(page).click();
  await expect(page).toHaveURL(/\/mypage$/);
  await back(page).click();
  await expect(page).toHaveURL(/\/trips$/);

  await page.goto("/mypage/alerts");                                                    // 주소로 바로 연 하위 화면: 앱 안에서 온 화면이 없다
  await back(page).click();
  await expect(page).toHaveURL(/\/mypage$/);
  await expect(page.getByRole("heading", { name: "설정", exact: true })).toBeVisible();
});

test("로그아웃하면 이 기기의 동의 사본과 취향 답도 지워져, 그 뒤 약관이 필요한 화면은 약관 화면으로 간다", async ({ page, request }) => {
  await mockServer(request).scenario({ sessionKind: "member" });
  await start(page);
  // 취향 설문을 마친 기기(답이 남아 있다)
  await page.addInitScript((key) => {
    if (!localStorage.getItem(key)) localStorage.setItem(key, JSON.stringify({ complete: true, step: 3, answers: { party: "", partyOther: "", priority: [], details: { food: [], activity: [], mobility: [] }, indoorDining: "", indoorActivity: "", pace: "relaxed", skipped: [0, 1, 2] } }));
  }, ONBOARDING_STORAGE);
  await page.goto("/trips");
  const stored = (key: string) => page.evaluate((name) => JSON.parse(localStorage.getItem(name) ?? "null") as Record<string, unknown> | null, key);
  expect(await stored(CONSENT_STORAGE)).not.toBeNull();
  expect(await stored(ONBOARDING_STORAGE)).toMatchObject({ complete: true, answers: { pace: "relaxed" } });

  await openAccountFromMenu(page);
  await page.locator("#main-content").getByRole("button", { name: "로그아웃", exact: true }).click();
  await page.getByRole("alertdialog", { name: "로그아웃할까요?" }).getByRole("button", { name: "로그아웃", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "로그아웃했어요" })).toBeVisible();
  await expect.poll(() => stored(CONSENT_STORAGE)).toBeNull();
  await expect.poll(() => stored(ONBOARDING_STORAGE)).toMatchObject({ complete: false, answers: { pace: "" } });

  await back(page).click();                                                             // 앱 안에서 설정 화면으로(새로 읽지 않는다 — 동의 사본을 다시 심지 않는다)
  await expect(page).toHaveURL(/\/start\?terms=required&returnTo=%2Fmypage$/);
  await expect(startCardHead(page, "terms")).toHaveAttribute("aria-expanded", "true");
});

test("소셜 로그인을 마친 뒤 티켓 없이 /auth/done 을 다시 열면 오류가 아니라 「로그인돼 있어요」를 보인다(게스트는 그대로 로그인하지 못했어요)", async ({ page }) => {
  await start(page);                                                                    // 게스트 세션 · 동의함
  await page.goto("/auth/done");
  await expect(page.getByRole("heading", { name: "로그인하지 못했어요" })).toBeVisible();   // 회원이 아니면 예전 그대로

  await page.goto("/mypage/account");
  await page.getByRole("group", { name: "소셜 계정" }).locator('li[data-provider="google"]').getByRole("button", { name: "Google 계정으로 계속" }).click();
  await expect(page.getByRole("heading", { name: "구글 계정으로 로그인했어요" })).toBeVisible();
  await page.goto("/auth/done");                                                        // 끝난 로그인 화면으로 다시 옴(티켓은 이미 썼다)
  await expect(page.getByRole("heading", { name: "로그인돼 있어요" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "로그인하지 못했어요" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "여행 목록 보기", exact: true })).toHaveAttribute("href", "/trips");
  await expect(page.getByRole("link", { name: "설정", exact: true })).toHaveAttribute("href", "/mypage");
});

test("세션이 끝났다는 오류(session_expired)면 여행 화면에 「여행을 등록한 계정으로 로그인」이 주 단추로 뜨고, 「여행 계획 등록」은 보조 단추가 된다", async ({ page }) => {
  await start(page);
  await page.route((url) => url.pathname.endsWith(`/v1/web/trips/${TRIP_ID}`), async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    const response = await route.fetch();
    await route.fulfill({ response, status: 401, json: { error: { code: "unauthenticated", message: "로그인 상태가 아니에요" } } });   // 서버가 세션을 모른다고 답했다
  });
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(page.getByRole("alert").filter({ hasText: "로그인 상태가 끝났어요" })).toBeVisible();
  // `[2026-10-19]` 56512ed1(알림 v5)이 이 화면에 자기 로그인 단추를 달았다 — 로그인하면 그 여행의 알림 센터로 돌아온다.
  const signIn = page.getByRole("link", { name: "여행을 등록한 계정으로 로그인", exact: true });
  await expect(signIn).toHaveAttribute("href", `/mypage/account?login=1&returnTo=${encodeURIComponent(`/trips/${TRIP_ID}?notices=1`)}`);
  await expect(signIn).toHaveClass(/primary/);
  await expect(page.getByRole("link", { name: "여행 계획 등록", exact: true })).toHaveClass(/secondary/);
});

test("계획을 「여행 등록」으로 여행으로 만들면 계획 담기의 글 초안이 지워져, 다음 새 여행 등록은 빈 칸으로 시작한다", async ({ page }) => {
  const PLAN = "10/1 09:00 경복궁 관람";
  await start(page);
  await beforeTheTrip(page);
  await openRegistration(page);
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  const draft = () => page.evaluate((key) => sessionStorage.getItem(key), DRAFT_STORAGE);
  await expect.poll(draft).toBe(PLAN);
  await checkPlan(page);
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);
  expect(await draft()).toBe(PLAN);                                                     // 계획 확인 화면까지는 초안이 남아 있다(돌아가 고칠 수 있게)
  await page.getByRole("button", { name: "여행 등록" }).click();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));
  await expect(tripScreen(page)).toBeVisible();
  expect(await draft()).toBeNull();
  await openRegistration(page);
  await expect(page.getByLabel("나의 여행 계획")).toHaveValue("");
});
