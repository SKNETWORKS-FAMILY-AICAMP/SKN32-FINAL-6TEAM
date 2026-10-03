import { expect, test, type Page } from "@playwright/test";
import { mockServer, noHorizontalScroll, start, useKorean } from "./helpers";

/**
 * My page and the profile edit screen, on the test mock server. (Ported from the old demo-build suite, 2026-10-03: the parts that were
 * about a demo build having no server — a disabled webhook row, "can be added only when connected" — are gone; saving the webhook is in
 * `webhook.spec.ts`, the token and its replacement in `keys.spec.ts`, social accounts in `social-login.spec.ts`.)
 */
const TOKEN = "acop_u_known";                 // the one key the mock server knows
const MASK = "••••••••••••••••";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

/** A browser that already holds the mock server's key. */
const withToken = (page: Page) => start(page);

test("메뉴 프로필 → 마이페이지 조회 → 수정 → 취소: 이미지 변경은 비활성, 토큰은 입력칸이 없고, 닉네임 초안은 어디에도 반영되지 않는다", async ({ page }) => {
  await withToken(page);
  await page.goto("/trips/new");
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  const profile = page.getByRole("dialog", { name: "메뉴" }).getByRole("link", { name: /마이페이지/ });
  await expect(profile).toContainText("닉네임 미발급");
  await profile.click();
  await expect(page).toHaveURL(/\/mypage$/);
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await expect(page.getByRole("heading", { name: "마이페이지", exact: true })).toBeVisible();
  await expect(page.locator("#main-content").getByText("닉네임 미발급", { exact: true })).toBeVisible();
  await expect(page.getByText(MASK)).toBeVisible();
  await expect(page.getByText(TOKEN)).toHaveCount(0);

  await page.getByRole("link", { name: "수정", exact: true }).click();
  await expect(page).toHaveURL(/\/mypage\/edit$/);
  await expect(page.getByRole("heading", { name: "프로필 수정", exact: true })).toBeVisible();
  const save = page.getByRole("button", { name: "저장", exact: true });
  await expect(save).toBeDisabled();
  await expect(page.getByText("디스코드 웹훅은 저장할 수 있어요. 닉네임·이미지 저장은 준비 중이에요.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "이미지 변경" })).toBeDisabled();
  await expect(page.getByText("이미지 변경은 준비 중이에요.", { exact: true })).toBeVisible();
  await expect(page.getByText("토큰은 수정할 수 없어요.", { exact: true })).toBeVisible();

  const nickname = page.getByLabel("닉네임");
  await expect(nickname).toHaveValue("");
  // The name line itself is the field: under the image, above the token, showing what My page shows.
  await expect(nickname).toHaveAttribute("placeholder", "닉네임 미발급");
  const [imageTop, fieldTop, tokenTop] = await Promise.all([page.locator('#main-content svg[class*="avatar"]'), nickname, page.getByText("발급된 토큰", { exact: true })]
    .map(async (item) => (await item.boundingBox())!.y));
  expect(imageTop < fieldTop && fieldTop < tokenTop).toBe(true);
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
  await expect(page.locator("#main-content").getByText("닉네임 미발급", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "메뉴" }).getByRole("link", { name: /마이페이지/ })).toContainText("닉네임 미발급");
  await page.keyboard.press("Escape");
  await page.getByRole("link", { name: "수정", exact: true }).click();
  await expect(page.getByLabel("닉네임")).toHaveValue("");
  // Nothing about the draft went to the server.
  expect((await mockServer(page.request).log()).filter((entry) => entry.method === "PUT")).toEqual([]);
});

test("토큰은 가려진 채 시작해 보기·숨기기로 바뀌고, 복사는 가린 채로도 토큰 전체를 복사하며, 다시 열면 다시 가려진다", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await withToken(page);
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
  await withToken(page);
  await page.addInitScript(() => Object.defineProperty(navigator, "clipboard", { value: { writeText: () => Promise.reject(new Error("denied")) } }));
  await page.goto("/mypage");
  await page.getByRole("button", { name: "복사", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "복사하지 못했어요." })).toBeVisible();
  await expect(page.getByText("토큰을 복사했어요.")).toHaveCount(0);
});

test("토큰이 없으면 미발급으로 보이고 보기·복사를 막으며, 마이페이지를 봐도 새 사용자 키를 만들지 않는다", async ({ page, request }) => {
  await useKorean(page);
  await page.goto("/mypage");
  await expect(page.getByText("발급된 토큰이 없어요.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "보기", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "복사", exact: true })).toBeDisabled();
  await page.getByRole("link", { name: "수정", exact: true }).click();
  await expect(page.getByText("발급된 토큰이 없어요.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "복사", exact: true })).toBeDisabled();
  expect(await page.evaluate(() => localStorage.getItem("tripilot.web.user-key.v1"))).toBeNull();
  expect((await mockServer(request).log()).filter((entry) => entry.path.endsWith("/v1/web/session"))).toEqual([]);
});

test("영어 화면과 PC·375px·320px에서 메뉴는 스크롤로 끝까지 닿고, 긴 토큰·닉네임이 잘리거나 가로로 넘치지 않는다", async ({ page }) => {
  await withToken(page);
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
  await expect(english.getByRole("link", { name: /My page/ })).toContainText("No nickname yet");
  await expect(english.getByRole("switch", { name: "Use floating button" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("heading", { name: "Edit profile", exact: true })).toBeVisible();
  await expect(page.getByText("You can save the Discord webhook. Saving the nickname and image is not available yet.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Change image" })).toBeDisabled();
  await expect(page.getByText("The token cannot be changed.", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Cancel", exact: true }).click();
  await expect(page.getByRole("heading", { name: "My page", exact: true })).toBeVisible();
});
