import { expect, test, type Page } from "@playwright/test";
import { mockServer, noHorizontalScroll, pickLanguage, start, useKorean, agree } from "./helpers";

/**
 * My page and the profile edit screen, on the test mock server. (Ported from the old demo-build suite, 2026-10-03: the parts that were
 * about a demo build having no server — a disabled webhook row, "can be added only when connected" — are gone; saving the webhook is in
 * `webhook.spec.ts`, the session in `session.spec.ts`, social accounts in `social-login.spec.ts`.)
 * ★`[2026-10-04]` There is no token to show, hide, copy or replace any more — the server gives a session cookie. What My page says about who
 *   this is, is the 「로그인 상태」 card (a guest, or a signed-in member).
 */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

/** A browser that already holds the mock server's session. */
const withSession = (page: Page) => start(page);

test("메뉴 프로필 칸 → 프로필 수정 → 취소: 이미지 변경은 비활성이고, 닉네임 초안은 어디에도 반영되지 않는다(게스트는 그 자리가 「로그인 · 가입」)", async ({ page, request }) => {
  // `[2026-10-13 회의 확정 — 메뉴 = 마이페이지]` 메뉴의 첫 칸이 프로필이다(이미지 · 이름 · 로그인 칩 · 단추 하나). 단추는 회원이면 「프로필 수정」, 그 밖에는 「로그인 · 가입」.
  await withSession(page);
  await page.goto("/trips/new");
  const open = page.getByRole("button", { name: "메뉴", exact: true });
  const menu = page.getByRole("dialog", { name: "메뉴" });
  await open.click();
  await expect(menu).toContainText("게스트 · 7일 뒤 지워져요");
  await expect(menu.getByRole("link", { name: "로그인 · 가입", exact: true })).toBeVisible();
  await expect(menu.getByRole("link", { name: "프로필 수정", exact: true })).toHaveCount(0);
  await page.keyboard.press("Escape");

  await mockServer(request).scenario({ sessionKind: "member" });
  await page.reload();
  await open.click();
  await expect(menu).toContainText("로그인됨");
  await menu.getByRole("link", { name: "프로필 수정", exact: true }).click();
  await expect(page).toHaveURL(/\/mypage\/edit$/);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "프로필 수정", exact: true })).toBeVisible();
  const save = page.getByRole("button", { name: "저장", exact: true });
  await expect(save).toBeDisabled();
  // `[2026-10-13 마이페이지 A안]` 수정 화면은 닉네임 · 이미지만 — 디스코드 웹훅은 설정의 「알림 받는 곳」 화면으로 옮겼다.
  await expect(page.getByText("닉네임 · 이미지 저장은 준비 중이에요. 디스코드 웹훅은 설정 › 「알림 받는 곳」에서 바꿔요.", { exact: true })).toBeVisible();
  await expect(page.getByLabel(/디스코드 웹훅 URL/)).toHaveCount(0);
  await expect(page.getByRole("button", { name: "이미지 변경" })).toBeDisabled();
  await expect(page.getByText("이미지 변경은 준비 중이에요.", { exact: true })).toBeVisible();
  await expect(page.getByText("토큰은 수정할 수 없어요.")).toHaveCount(0);

  const nickname = page.getByLabel("닉네임");
  await expect(nickname).toHaveValue("");
  // The name line itself is the field: under the image, showing what the menu's profile shows.
  await expect(nickname).toHaveAttribute("placeholder", "로그인한 사용자");
  const [imageTop, fieldTop] = await Promise.all([page.locator('#main-content svg[class*="avatar"]'), nickname]
    .map(async (item) => (await item.boundingBox())!.y));
  expect(imageTop < fieldTop).toBe(true);
  await nickname.fill("여행자");
  await nickname.fill("   ");
  await expect(page.getByText("닉네임을 입력해 주세요.", { exact: true })).toBeVisible();
  await expect(nickname).toHaveAttribute("aria-invalid", "true");
  await nickname.fill("새 여행자");
  await expect(page.getByText("닉네임을 입력해 주세요.")).toHaveCount(0);

  // The nickname has no server call yet, so a typed nickname alone saves nothing. 「취소」 goes back to the screen the menu was opened on.
  await expect(save).toBeDisabled();
  await page.getByRole("button", { name: "취소", exact: true }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await open.click();
  await expect(menu).toContainText("로그인한 사용자");
  await menu.getByRole("link", { name: "프로필 수정", exact: true }).click();
  await expect(page.getByLabel("닉네임")).toHaveValue("");
  // Nothing about the draft went to the server.
  expect((await mockServer(page.request).log()).filter((entry) => entry.method === "PUT")).toEqual([]);
});

test("세션이 없으면 「아직 시작하지 않았어요」로 보이고, 설정 화면을 봐도 새 사용자(게스트 세션)를 만들지 않는다", async ({ page, request }) => {
  await useKorean(page);
  await agree(page);                                                                  // 약관에는 동의했지만 세션은 아직 없는 사람(동의만으로는 서버가 사용자를 만들지 않는다: 서버에 보낼 때 만들어진다)
  await page.goto("/mypage");
  await expect(page.getByRole("navigation", { name: "내 상태" }).getByRole("link", { name: /^로그인 · 계정/ })).toContainText("아직 시작하지 않았어요");
  await page.goto("/mypage/edit");                                                   // `[2026-10-13]` 설정 화면에는 「프로필 수정」이 없다(메뉴의 회원 단추)
  await expect(page.getByRole("heading", { name: "프로필 수정", exact: true })).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("tripilot.web.user-key.v1"))).toBeNull();
  const log = await mockServer(request).log();
  expect(log.filter((entry) => entry.method === "POST" && entry.path.endsWith("/v1/web/auth/session"))).toEqual([]);
});

test("서버에 연결하지 못하면 설정 화면은 그렇다고 말한다(게스트인지 모른다고 지어내지 않는다)", async ({ page }) => {
  await withSession(page);
  await page.route("**/v1/web/auth/me", (route) => route.abort());
  await page.goto("/mypage");
  await expect(page.getByRole("navigation", { name: "내 상태" }).getByRole("link", { name: /^로그인 · 계정/ })).toContainText("서버에 연결하지 못해");
  await page.goto("/mypage/account");
  await expect(page.getByRole("group", { name: "로그인 상태" })).toContainText("서버에 연결하지 못해");
});

test("영어 화면과 PC·375px·320px에서 메뉴는 스크롤로 끝까지 닿고, 긴 닉네임이 잘리거나 가로로 넘치지 않는다", async ({ page }) => {
  await withSession(page);
  const long = "아주긴닉네임".repeat(10);
  for (const [width, height] of [[1280, 900], [375, 812], [320, 640]]) {
    await page.setViewportSize({ width, height });
    await page.goto("/mypage/account");                                          // `[2026-10-13]` 로그인 상태 카드는 「로그인 · 계정」 화면
    await page.getByRole("button", { name: "메뉴", exact: true }).click();
    const menu = page.getByRole("dialog", { name: "메뉴" });
    const last = menu.getByRole("link", { name: /^설정/ });                          // `[2026-10-13]` 메뉴의 마지막 줄(앱 설정은 설정 화면으로 옮겼다)
    await last.scrollIntoViewIfNeeded();
    await expect(last).toBeInViewport();
    expect(await menu.evaluate((panel) => panel.scrollWidth <= panel.clientWidth)).toBe(true);
    await noHorizontalScroll(page);
    await page.keyboard.press("Escape");

    // the status card and its long sentences stay inside the card
    const status = page.getByRole("group", { name: "로그인 상태" });
    await expect(status).toBeVisible();
    await noHorizontalScroll(page);
    const inside = await status.evaluate((element) => {
      const box = element.getBoundingClientRect(), card = element.closest("section")!.getBoundingClientRect();
      return box.left >= card.left && box.right <= card.right;
    });
    expect(inside, `${width}x${height}`).toBe(true);

    await page.goto("/mypage/edit");
    await page.getByLabel("닉네임").fill(long);
    await noHorizontalScroll(page);
    // Phones keep 16px text in fields (no zoom on focus); wider screens keep the design's size.
    for (const input of [page.getByLabel("닉네임")]) {
      const size = await input.evaluate((element) => parseFloat(getComputedStyle(element).fontSize));
      expect(size, `${width}x${height}`).toBeGreaterThanOrEqual(width <= 550 ? 16 : 14);
    }
  }

  await pickLanguage(page, "메뉴", "English");                                     // `[2026-10-13]` 언어는 설정 화면에서 고르고 수정 화면으로 돌아온다
  await page.getByRole("button", { name: "Menu", exact: true }).click();
  const english = page.getByRole("dialog", { name: "Menu" });
  await expect(english).toContainText("Guest");
  await expect(english.getByRole("link", { name: /^Settings/ })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("heading", { name: "Edit profile", exact: true })).toBeVisible();
  await expect(page.getByText("Saving the nickname and image is not available yet. The Discord webhook is changed in Settings → “Where alerts go”.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Change image" })).toBeDisabled();
  await page.goto("/mypage");
  await expect(page.getByRole("heading", { name: "Settings", exact: true })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "My status" }).getByRole("link", { name: /^Sign-in & accounts/ })).toContainText("Guest");
});
