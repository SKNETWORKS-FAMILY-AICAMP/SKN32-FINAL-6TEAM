import { expect, test } from "@playwright/test";
import { registerExampleTrip, useKorean } from "./helpers/app";

test.beforeEach(async ({ page }) => { await useKorean(page); });

test("메뉴는 프로필·여행 목록·언어·플로팅 스위치 순서이고, Tab 순환과 Esc(언어 목록 먼저, 메뉴 다음)·포커스 복귀를 지키며, 링크는 메뉴를 닫는다", async ({ page }) => {
  await page.goto("/trips/new");
  const open = page.getByRole("button", { name: "메뉴", exact: true });
  await open.click();
  const menu = page.getByRole("dialog", { name: "메뉴" });
  const profile = menu.getByRole("link", { name: /마이페이지/ });
  const trips = menu.getByRole("link", { name: "여행 목록 보기" });
  const language = menu.getByRole("button", { name: /LANGUAGE/ });
  const floating = menu.getByRole("switch", { name: "플로팅 버튼 사용" });
  const close = menu.getByRole("button", { name: "메뉴 닫기" });
  const tops = await Promise.all([profile, trips, language, floating].map(async (item) => (await item.boundingBox())!.y));
  expect([...tops].sort((a, b) => a - b)).toEqual(tops);
  // One board holds exactly these four rows; the language row is the home card's picker with its caption.
  expect(await profile.evaluate((link) => {
    const board = link.parentElement!;
    return board.children.length === 4 && Boolean(board.querySelector('a[href="/trips"]')) && Boolean(board.querySelector('[role="switch"]')) && board.textContent!.includes("LANGUAGE · 언어");
  })).toBe(true);

  await expect(profile).toBeFocused();
  for (const next of [trips, language, floating, close, profile]) {
    await page.keyboard.press("Tab");
    await expect(next).toBeFocused();
  }
  await page.keyboard.press("Shift+Tab");
  await expect(close).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(floating).toBeFocused();

  // The language card opens with Enter, its options join the cycle, and Escape closes the list before the menu.
  await language.focus();
  await page.keyboard.press("Enter");
  await expect(language).toHaveAttribute("aria-expanded", "true");
  await page.keyboard.press("Tab");
  await expect(menu.getByRole("button", { name: "English", exact: true })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(language).toHaveAttribute("aria-expanded", "false");
  await expect(language).toBeFocused();
  await expect(menu).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(menu).toHaveCount(0);
  await expect(open).toBeFocused();

  await open.click();
  await page.keyboard.press("Tab");
  await expect(trips).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/trips$/);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await open.click();
  await trips.click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page).toHaveURL(/\/trips$/);
});

test("메뉴의 언어 카드는 홈 카드처럼 펼쳐 고르면 바로 적용·접히고, 홈 카드와 같은 설정을 쓴다", async ({ page }) => {
  await page.goto("/");
  const home = page.locator("main").getByRole("button", { name: /LANGUAGE/ });
  await expect(home).toContainText("한국어");
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  const menu = page.getByRole("dialog", { name: "메뉴" });
  const toggle = menu.getByRole("button", { name: /LANGUAGE/ });
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(toggle).toContainText("한국어");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await expect(menu.getByRole("button", { name: "한국어", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(menu.getByRole("button", { name: "English", exact: true })).toHaveAttribute("aria-pressed", "false");
  await menu.getByRole("button", { name: "English", exact: true }).click();

  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  const english = page.getByRole("dialog", { name: "Menu" }).getByRole("button", { name: /LANGUAGE/ });
  await expect(english).toHaveAttribute("aria-expanded", "false");
  await expect(english).toBeFocused();
  await expect(english).toContainText("English");
  await page.keyboard.press("Escape");
  await expect(home).toContainText("English");
  await expect(page.locator("#intro-title")).toContainText("From plans to memories");

  await home.click();
  await page.getByRole("button", { name: "한국어", exact: true }).click();
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "메뉴" }).getByRole("button", { name: /LANGUAGE/ })).toContainText("한국어");
});

test("플로팅 버튼 스위치는 기본 OFF(고정 하단 탭)이고, 켜면 플로팅 버튼으로 바로 바뀌어 새로고침 뒤에도 유지된다", async ({ page }) => {
  await registerExampleTrip(page);
  const fixedTab = page.locator("#trip-pane-button-schedule");
  const floatingButton = page.getByRole("button", { name: "일정 · 메뉴 열기 또는 닫기" });
  await expect(fixedTab).toBeVisible();
  await expect(floatingButton).toBeHidden();

  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  const floating = page.getByRole("dialog", { name: "메뉴" }).getByRole("switch", { name: "플로팅 버튼 사용" });
  await expect(floating).not.toBeChecked();
  await floating.focus();
  await page.keyboard.press("Space");
  await expect(floating).toBeChecked();
  await page.keyboard.press("Escape");
  await expect(fixedTab).toBeHidden();
  await expect(floatingButton).toBeVisible();

  await page.reload();
  await expect(floatingButton).toBeVisible();
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await expect(floating).toBeChecked();
  await floating.click();
  await expect(floating).not.toBeChecked();
  await page.keyboard.press("Escape");
  await expect(fixedTab).toBeVisible();
  await expect(floatingButton).toBeHidden();
});
