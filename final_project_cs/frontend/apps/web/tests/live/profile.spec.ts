import { expect, test, type Page } from "@playwright/test";
import { mockServer, noHorizontalScroll, start, useKorean, agree } from "./helpers";

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

test("메뉴 프로필 → 마이페이지 조회 → 수정 → 취소: 이미지 변경은 비활성이고, 닉네임 초안은 어디에도 반영되지 않는다", async ({ page }) => {
  await withSession(page);
  await page.goto("/trips/new");
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  const profile = page.getByRole("dialog", { name: "메뉴" }).getByRole("link", { name: /마이페이지/ });
  await expect(profile).toContainText("게스트");
  await profile.click();
  await expect(page).toHaveURL(/\/mypage$/);
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await expect(page.getByRole("heading", { name: "마이페이지", exact: true })).toBeVisible();
  await expect(page.locator("#main-content").getByText("게스트", { exact: true })).toBeVisible();
  await expect(page.getByText("발급된 토큰")).toHaveCount(0);

  await page.getByRole("link", { name: "수정", exact: true }).click();
  await expect(page).toHaveURL(/\/mypage\/edit$/);
  await expect(page.getByRole("heading", { name: "프로필 수정", exact: true })).toBeVisible();
  const save = page.getByRole("button", { name: "저장", exact: true });
  await expect(save).toBeDisabled();
  await expect(page.getByText("디스코드 웹훅은 저장할 수 있어요. 닉네임·이미지 저장은 준비 중이에요.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "이미지 변경" })).toBeDisabled();
  await expect(page.getByText("이미지 변경은 준비 중이에요.", { exact: true })).toBeVisible();
  await expect(page.getByText("토큰은 수정할 수 없어요.")).toHaveCount(0);

  const nickname = page.getByLabel("닉네임");
  await expect(nickname).toHaveValue("");
  // The name line itself is the field: under the image, above the webhook, showing what My page shows.
  await expect(nickname).toHaveAttribute("placeholder", "게스트");
  const [imageTop, fieldTop, webhookTop] = await Promise.all([page.locator('#main-content svg[class*="avatar"]'), nickname, page.getByLabel(/디스코드 웹훅 URL/)]
    .map(async (item) => (await item.boundingBox())!.y));
  expect(imageTop < fieldTop && fieldTop < webhookTop).toBe(true);
  await nickname.fill("여행자");
  await nickname.fill("   ");
  await expect(page.getByText("닉네임을 입력해 주세요.", { exact: true })).toBeVisible();
  await expect(nickname).toHaveAttribute("aria-invalid", "true");
  await nickname.fill("새 여행자");
  await expect(page.getByText("닉네임을 입력해 주세요.")).toHaveCount(0);

  // The nickname has no server call yet, so a typed nickname alone saves nothing.
  await expect(save).toBeDisabled();
  await page.getByRole("link", { name: "취소", exact: true }).click();
  await expect(page).toHaveURL(/\/mypage$/);
  await expect(page.locator("#main-content").getByText("게스트", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "메뉴" }).getByRole("link", { name: /마이페이지/ })).toContainText("게스트");
  await page.keyboard.press("Escape");
  await page.getByRole("link", { name: "수정", exact: true }).click();
  await expect(page.getByLabel("닉네임")).toHaveValue("");
  // Nothing about the draft went to the server.
  expect((await mockServer(page.request).log()).filter((entry) => entry.method === "PUT")).toEqual([]);
});

test("세션이 없으면 「아직 시작하지 않았어요」로 보이고, 마이페이지를 봐도 새 사용자(게스트 세션)를 만들지 않는다", async ({ page, request }) => {
  await useKorean(page);
  await agree(page);                                                                  // 약관에는 동의했지만 세션은 아직 없는 사람(동의만으로는 서버가 사용자를 만들지 않는다: 서버에 보낼 때 만들어진다)
  await page.goto("/mypage");
  await expect(page.getByRole("group", { name: "로그인 상태" })).toContainText("아직 시작하지 않았어요");
  await page.getByRole("link", { name: "수정", exact: true }).click();
  await expect(page.getByRole("heading", { name: "프로필 수정", exact: true })).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("tripilot.web.user-key.v1"))).toBeNull();
  const log = await mockServer(request).log();
  expect(log.filter((entry) => entry.method === "POST" && entry.path.endsWith("/v1/web/auth/session"))).toEqual([]);
});

test("서버에 연결하지 못하면 마이페이지는 그렇다고 말한다(게스트인지 모른다고 지어내지 않는다)", async ({ page }) => {
  await withSession(page);
  await page.route("**/v1/web/auth/me", (route) => route.abort());
  await page.goto("/mypage");
  await expect(page.getByRole("group", { name: "로그인 상태" })).toContainText("서버에 연결하지 못해");
});

test("영어 화면과 PC·375px·320px에서 메뉴는 스크롤로 끝까지 닿고, 긴 닉네임이 잘리거나 가로로 넘치지 않는다", async ({ page }) => {
  await withSession(page);
  const long = "아주긴닉네임".repeat(10);
  for (const [width, height] of [[1280, 900], [375, 812], [320, 640]]) {
    await page.setViewportSize({ width, height });
    await page.goto("/mypage");
    await page.getByRole("button", { name: "메뉴", exact: true }).click();
    const menu = page.getByRole("dialog", { name: "메뉴" });
    await menu.getByRole("button", { name: /LANGUAGE/ }).click();
    const floating = menu.getByRole("switch", { name: "플로팅 버튼 사용" });
    await floating.scrollIntoViewIfNeeded();
    await expect(floating).toBeInViewport();
    expect(await menu.evaluate((panel) => panel.scrollWidth <= panel.clientWidth)).toBe(true);
    await noHorizontalScroll(page);
    await page.keyboard.press("Escape");
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

    await page.getByRole("link", { name: "수정", exact: true }).click();
    await page.getByLabel("닉네임").fill(long);
    await noHorizontalScroll(page);
    // Phones keep 16px text in fields (no zoom on focus); wider screens keep the design's size.
    for (const input of [page.getByLabel("닉네임")]) {
      const size = await input.evaluate((element) => parseFloat(getComputedStyle(element).fontSize));
      expect(size, `${width}x${height}`).toBeGreaterThanOrEqual(width <= 550 ? 16 : 14);
    }
  }

  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  const menu = page.getByRole("dialog", { name: "메뉴" });
  await menu.getByRole("button", { name: /LANGUAGE/ }).click();
  await menu.getByRole("button", { name: "English", exact: true }).click();
  const english = page.getByRole("dialog", { name: "Menu" });
  await expect(english.getByRole("link", { name: /My page/ })).toContainText("Guest");
  await expect(english.getByRole("switch", { name: "Use floating button" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("heading", { name: "Edit profile", exact: true })).toBeVisible();
  await expect(page.getByText("You can save the Discord webhook. Saving the nickname and image is not available yet.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Change image" })).toBeDisabled();
  await page.getByRole("link", { name: "Cancel", exact: true }).click();
  await expect(page.getByRole("heading", { name: "My page", exact: true })).toBeVisible();
  await expect(page.getByRole("group", { name: "Sign-in status" })).toContainText("You are using triPilot as a guest");
});
