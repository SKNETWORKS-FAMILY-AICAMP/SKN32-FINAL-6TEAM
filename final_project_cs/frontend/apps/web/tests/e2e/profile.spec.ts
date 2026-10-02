import { expect, test, type Page } from "@playwright/test";
import { noHorizontalScroll, useKorean } from "./helpers/app";

/** A test-only user key, stored where the live connection keeps the real one. Never a real token. */
const TOKEN = `acop_u_e2e_test_${"0123456789abcdef".repeat(6)}`;
const MASK = "••••••••••••••••";

test.beforeEach(async ({ page }) => { await useKorean(page); });

async function withTestToken(page: Page) {
  await page.addInitScript((token) => localStorage.setItem("tripilot.web.user-key.v1", token), TOKEN);
}

test("메뉴 프로필 → 마이페이지 조회 → 수정 → 취소: 이미지 변경·저장은 비활성, 토큰은 입력칸이 없고, 이메일은 선택이며 초안은 어디에도 반영되지 않는다", async ({ page }) => {
  await withTestToken(page);
  await page.goto("/trips/new");
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  const profile = page.getByRole("dialog", { name: "메뉴" }).getByRole("link", { name: /마이페이지/ });
  await expect(profile).toContainText("닉네임 미발급");
  await profile.click();
  await expect(page).toHaveURL(/\/mypage$/);
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await expect(page.getByRole("heading", { name: "마이페이지", exact: true })).toBeVisible();
  await expect(page.locator("#main-content").getByText("닉네임 미발급", { exact: true })).toBeVisible();
  // The name line under the image is the only nickname: no second 「닉네임」 row.
  await expect(page.locator("#main-content dt")).toHaveText(["발급된 토큰", "토큰 복구용 이메일"]);
  await expect(page.getByText("등록된 이메일이 없습니다.", { exact: true })).toBeVisible();
  await expect(page.getByText(MASK)).toBeVisible();
  await expect(page.getByText(TOKEN)).toHaveCount(0);
  await expect(page.locator("#main-content input")).toHaveCount(0);

  await page.getByRole("link", { name: "수정", exact: true }).click();
  await expect(page).toHaveURL(/\/mypage\/edit$/);
  await expect(page.getByRole("heading", { name: "프로필 수정", exact: true })).toBeVisible();
  const save = page.getByRole("button", { name: "저장", exact: true });
  await expect(save).toBeDisabled();
  await expect(page.getByText("이메일은 저장할 수 있어요. 닉네임·이미지 저장은 준비 중이에요.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "이미지 변경" })).toBeDisabled();
  await expect(page.getByText("이미지 변경은 준비 중이에요.", { exact: true })).toBeVisible();
  // Only the nickname and the email are fields; the token is shown, never edited.
  await expect(page.locator("#main-content input")).toHaveCount(2);
  await expect(page.getByText("토큰은 수정할 수 없어요.", { exact: true })).toBeVisible();

  const nickname = page.getByLabel("닉네임");
  await expect(nickname).toHaveValue("");
  // The name line itself is the field: under the image, above the token, showing what My page shows.
  await expect(nickname).toHaveAttribute("placeholder", "닉네임 미발급");
  const [imageTop, fieldTop, tokenTop] = await Promise.all([page.locator("#main-content img").first(), nickname, page.getByText("발급된 토큰", { exact: true })]
    .map(async (item) => (await item.boundingBox())!.y));
  expect(imageTop < fieldTop && fieldTop < tokenTop).toBe(true);
  await nickname.fill("여행자");
  await nickname.fill("   ");
  await expect(page.getByText("닉네임을 입력해 주세요.", { exact: true })).toBeVisible();
  await expect(nickname).toHaveAttribute("aria-invalid", "true");
  await nickname.fill("새 여행자");
  await expect(page.getByText("닉네임을 입력해 주세요.")).toHaveCount(0);

  const email = page.getByLabel(/토큰 복구용 이메일/);
  await email.fill("not-an-email");
  await expect(page.getByText("이메일 형식이 올바르지 않아요.", { exact: true })).toBeVisible();
  await expect(save).toBeDisabled();
  await email.fill("traveler@example.com");
  await expect(page.getByText("이메일 형식이 올바르지 않아요.")).toHaveCount(0);
  // ★`[2026-10-01]` A changed, well-formed email can be saved (in this browser). Cancel below drops this draft.
  await expect(save).toBeEnabled();
  await email.fill("");
  await expect(page.getByText("이메일 형식이 올바르지 않아요.")).toHaveCount(0);
  await expect(page.getByText("토큰을 잃어버렸을 때 찾는 데 사용할 이메일이에요.", { exact: true })).toBeVisible();
  // Back to what is saved (nothing): nothing changed, so there is nothing to save.
  await expect(save).toBeDisabled();

  await email.fill("traveler@example.com");
  await page.getByRole("link", { name: "취소", exact: true }).click();
  await expect(page).toHaveURL(/\/mypage$/);
  await expect(page.locator("#main-content").getByText("닉네임 미발급", { exact: true })).toBeVisible();
  // Cancel dropped the draft: no email was registered.
  await expect(page.getByText("등록된 이메일이 없습니다.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "메뉴" }).getByRole("link", { name: /마이페이지/ })).toContainText("닉네임 미발급");
  await page.keyboard.press("Escape");
  await page.getByRole("link", { name: "수정", exact: true }).click();
  await expect(page.getByLabel("닉네임")).toHaveValue("");
});

test("토큰은 가려진 채 시작해 보기·숨기기로 바뀌고, 복사는 가린 채로도 토큰 전체를 복사하며, 다시 열면 다시 가려진다", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await withTestToken(page);
  await page.goto("/mypage");
  await expect(page.getByText(MASK)).toBeVisible();
  await page.getByRole("button", { name: "보기", exact: true }).click();
  await expect(page.getByText(TOKEN, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "숨기기", exact: true }).click();
  await expect(page.getByText(TOKEN)).toHaveCount(0);

  await page.getByRole("button", { name: "복사", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "토큰을 복사했어요." })).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(TOKEN);

  await page.getByRole("button", { name: "보기", exact: true }).click();
  await page.getByRole("link", { name: "수정", exact: true }).click();
  await expect(page.getByText(MASK)).toBeVisible();
  await page.getByRole("link", { name: "취소", exact: true }).click();
  await expect(page.getByText(MASK)).toBeVisible();
  await expect(page.getByText(TOKEN)).toHaveCount(0);
});

test("복사가 실패하면 실패했다고 알린다", async ({ page }) => {
  await withTestToken(page);
  await page.addInitScript(() => Object.defineProperty(navigator, "clipboard", { value: { writeText: () => Promise.reject(new Error("denied")) } }));
  await page.goto("/mypage");
  await page.getByRole("button", { name: "복사", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "복사하지 못했어요." })).toBeVisible();
  await expect(page.getByText("토큰을 복사했어요.")).toHaveCount(0);
});

test("토큰이 없으면 미발급으로 보이고 보기·복사를 막으며, 마이페이지를 봐도 새 사용자 키를 만들지 않는다", async ({ page }) => {
  await page.goto("/mypage");
  await expect(page.getByText("발급된 토큰이 없어요.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "보기", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "복사", exact: true })).toBeDisabled();
  await page.getByRole("link", { name: "수정", exact: true }).click();
  await expect(page.getByText("발급된 토큰이 없어요.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "복사", exact: true })).toBeDisabled();
  expect(await page.evaluate(() => localStorage.getItem("tripilot.web.user-key.v1"))).toBeNull();
});

test("영어 화면과 PC·375px·320px에서 메뉴는 스크롤로 끝까지 닿고, 긴 토큰·닉네임·이메일이 잘리거나 가로로 넘치지 않는다", async ({ page }) => {
  await withTestToken(page);
  const long = "아주긴닉네임".repeat(10);
  const longEmail = `${"traveler.with.a.very.long.name".repeat(3)}@example-travel-domain.com`;
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

    await page.getByRole("button", { name: "보기", exact: true }).click();
    await expect(page.getByText(TOKEN, { exact: true })).toBeVisible();
    await noHorizontalScroll(page);
    const inside = await page.getByText(TOKEN, { exact: true }).evaluate((element) => {
      const box = element.getBoundingClientRect(), card = element.closest("section")!.getBoundingClientRect();
      return box.left >= card.left && box.right <= card.right;
    });
    expect(inside, `${width}x${height}`).toBe(true);

    await page.getByRole("link", { name: "수정", exact: true }).click();
    await page.getByLabel("닉네임").fill(long);
    await page.getByLabel(/토큰 복구용 이메일/).fill(longEmail);
    await noHorizontalScroll(page);
    // Phones keep 16px text in fields (no zoom on focus); wider screens keep the design's size.
    for (const input of [page.getByLabel("닉네임"), page.getByLabel(/토큰 복구용 이메일/)]) {
      const size = await input.evaluate((element) => parseFloat(getComputedStyle(element).fontSize));
      expect(size, `${width}x${height}`).toBeGreaterThanOrEqual(width <= 550 ? 16 : 14);
    }
  }

  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  const menu = page.getByRole("dialog", { name: "메뉴" });
  await menu.getByRole("button", { name: /LANGUAGE/ }).click();
  await menu.getByRole("button", { name: "English", exact: true }).click();
  const english = page.getByRole("dialog", { name: "Menu" });
  await expect(english.getByRole("link", { name: /My page/ })).toContainText("No nickname yet");
  await expect(english.getByRole("switch", { name: "Use floating button" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("heading", { name: "Edit profile", exact: true })).toBeVisible();
  await expect(page.getByText("You can save the email. Saving the nickname and image is not available yet.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Change image" })).toBeDisabled();
  await expect(page.getByText("The token cannot be changed.", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Cancel", exact: true }).click();
  await expect(page.getByRole("heading", { name: "My page", exact: true })).toBeVisible();
  await expect(page.getByText("No email registered.", { exact: true })).toBeVisible();
});

test("이메일 등록 → 마이페이지에 보임 → 새로고침 뒤에도 남음 → 바꾸기 → 비우고 저장하면 지워진다", async ({ page }) => {
  await withTestToken(page);
  await page.goto("/mypage");
  await expect(page.getByText("등록된 이메일이 없습니다.", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "이메일 등록하기" }).click();
  await expect(page).toHaveURL(/\/mypage\/edit$/);
  const save = page.getByRole("button", { name: "저장", exact: true });
  const email = page.getByLabel(/토큰 복구용 이메일/);
  await email.fill("a@b");
  await expect(save).toBeDisabled();
  await email.fill("  traveler@example.com  ");
  await save.click();
  await expect(page).toHaveURL(/\/mypage$/);
  await expect(page.locator("#main-content").getByText("traveler@example.com", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "이메일 등록하기" })).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.getItem("tripilot.web.contact.v1"))).toBe(JSON.stringify({ recoveryEmail: "traveler@example.com", pending: true }));   // demo build: no server, so it stays in this browser

  await page.reload();
  await expect(page.locator("#main-content").getByText("traveler@example.com", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "수정", exact: true }).click();
  await expect(page.getByLabel(/토큰 복구용 이메일/)).toHaveValue("traveler@example.com");
  await expect(page.getByRole("button", { name: "저장", exact: true })).toBeDisabled();
  await page.getByLabel(/토큰 복구용 이메일/).fill("");
  await page.getByRole("button", { name: "저장", exact: true }).click();
  await expect(page).toHaveURL(/\/mypage$/);
  await expect(page.getByText("등록된 이메일이 없습니다.", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("tripilot.web.contact.v1"))).toBeNull();
});
