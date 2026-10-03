import { expect, test } from "@playwright/test";
import { mockServer, registerStubTrip, useKorean } from "./helpers";

test.beforeEach(async ({ page, request }) => { await mockServer(request).reset(); await useKorean(page); });

test("메뉴는 프로필·여행 목록·언어·테마·플로팅 스위치 순서이고, Tab 순환과 Esc(언어 목록 먼저, 메뉴 다음)·포커스 복귀를 지키며, 링크는 메뉴를 닫는다", async ({ page, request }) => {
  // The six base rows (profile · trips · language · theme · floating switch · skip-animation switch): with a social sign-in provider set up the menu has a seventh (「계정 연결 · 로그인」, covered by social-login.spec).
  await mockServer(request).scenario({ social: "off" });
  await page.goto("/trips/new");
  const open = page.getByRole("button", { name: "메뉴", exact: true });
  await open.click();
  const menu = page.getByRole("dialog", { name: "메뉴" });
  const profile = menu.getByRole("link", { name: /마이페이지/ });
  const trips = menu.getByRole("link", { name: "여행 목록 보기" });
  const language = menu.getByRole("button", { name: /LANGUAGE/ });
  const green = menu.getByRole("button", { name: "그린", exact: true });
  const white = menu.getByRole("button", { name: "화이트", exact: true });
  const floating = menu.getByRole("switch", { name: "플로팅 버튼 사용" });
  const skip = menu.getByRole("switch", { name: "애니메이션 건너뛰기" });
  const close = menu.getByRole("button", { name: "메뉴 닫기" });
  const tops = await Promise.all([profile, trips, language, green, floating, skip].map(async (item) => (await item.boundingBox())!.y));
  expect([...tops].sort((a, b) => a - b)).toEqual(tops);
  // One board holds exactly these six rows; the language row is the home card's picker with its caption.
  expect(await profile.evaluate((link) => {
    const board = link.parentElement!;
    return board.children.length === 6 && Boolean(board.querySelector('a[href="/trips"]')) && Boolean(board.querySelector('[role="switch"]')) && board.textContent!.includes("LANGUAGE · 언어") && board.textContent!.includes("THEME · 테마");
  })).toBe(true);

  await expect(profile).toBeFocused();
  for (const next of [trips, language, green, white, floating, skip, close, profile]) {
    await page.keyboard.press("Tab");
    await expect(next).toBeFocused();
  }
  await page.keyboard.press("Shift+Tab");
  await expect(close).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(skip).toBeFocused();

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
  await expect(profile).toBeFocused();   // 메뉴가 열려 초점을 받은 뒤에 Tab 을 누른다(위와 같다)
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

test("메뉴의 언어 카드를 펼쳐 고르면 바로 적용·접히고, 첫 화면에는 언어 카드가 없다(2026-10-03 사용자 결정 — 언어는 메뉴에만)", async ({ page }) => {
  await page.goto("/");
  const home = page.locator("main").getByRole("button", { name: /LANGUAGE/ });
  await expect(home).toHaveCount(0);
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
  await expect(home).toHaveCount(0);
  await expect(page.locator("#intro-title")).toContainText("From plans to memories");

  // Back to Korean through the menu — the only place the card lives.
  await page.getByRole("button", { name: "Menu", exact: true }).click();
  const englishMenu = page.getByRole("dialog", { name: "Menu" });
  await englishMenu.getByRole("button", { name: /LANGUAGE/ }).click();
  await englishMenu.getByRole("button", { name: "한국어", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "ko");
  await expect(page.getByRole("dialog", { name: "메뉴" }).getByRole("button", { name: /LANGUAGE/ })).toContainText("한국어");
});

test("플로팅 버튼 스위치는 기본 OFF(고정 하단 탭)이고, 켜면 플로팅 버튼으로 바로 바뀌어 새로고침 뒤에도 유지된다", async ({ page }) => {
  await registerStubTrip(page);
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

test("테마 카드에서 화이트를 고르면 모든 화면에 바로 적용되고, 새로고침 뒤에는 첫 화면을 그리기 전에 적용된다", async ({ page }) => {
  // When the saved theme lands on <html>: before <body> exists means before the first paint (no green flash).
  await page.addInitScript(() => {
    new MutationObserver(() => {
      if (document.documentElement?.dataset.theme === "neutral" && !("themeBeforeBody" in window)) Object.assign(window, { themeBeforeBody: document.body === null });
    }).observe(document, { subtree: true, childList: true, attributes: true, attributeFilter: ["data-theme"] });
  });
  await page.goto("/trips");
  const html = page.locator("html");
  const background = () => page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  await expect(html).toHaveAttribute("data-theme", "green");
  expect(await background()).toBe("rgb(243, 245, 243)");

  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  const card = page.getByRole("dialog", { name: "메뉴" }).getByRole("group", { name: /THEME/ });
  const green = card.getByRole("button", { name: "그린", exact: true });
  const white = card.getByRole("button", { name: "화이트", exact: true });
  await expect(green).toHaveAttribute("aria-pressed", "true");
  await white.click();
  await expect(white).toHaveAttribute("aria-pressed", "true");
  await expect(green).toHaveAttribute("aria-pressed", "false");
  await expect(card).toContainText("화이트");
  await expect(html).toHaveAttribute("data-theme", "neutral");
  expect(await background()).toBe("rgb(242, 242, 239)");
  // Each sample keeps its own theme's colours, whichever is chosen; the chosen option uses the selection colour.
  const sample = (option: typeof green) => option.locator("[data-theme] > span").evaluate((dot) => getComputedStyle(dot).backgroundColor);
  expect([await sample(green), await sample(white)]).toEqual(["rgb(46, 96, 71)", "rgb(28, 28, 30)"]);
  expect(await white.evaluate((option) => getComputedStyle(option).borderColor)).toBe("rgb(36, 87, 214)");

  await page.keyboard.press("Escape");
  await page.reload();
  await expect(html).toHaveAttribute("data-theme", "neutral");
  expect(await page.evaluate(() => (window as unknown as { themeBeforeBody?: boolean }).themeBeforeBody)).toBe(true);
  expect(await background()).toBe("rgb(242, 242, 239)");

  // Another screen follows the same choice; choosing green again returns every colour.
  await page.goto("/start");
  await expect(html).toHaveAttribute("data-theme", "neutral");
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await page.getByRole("dialog", { name: "메뉴" }).getByRole("button", { name: "그린", exact: true }).click();
  await expect(html).toHaveAttribute("data-theme", "green");
  expect(await background()).toBe("rgb(243, 245, 243)");
});

test("「애니메이션 건너뛰기」 스위치는 기본 꺼짐이고, 켜면 이 브라우저가 기억해 새로고침 뒤에도 켜져 있다(시스템의 「동작 줄이기」와 별개)", async ({ page, request }) => {
  await mockServer(request).scenario({ social: "off" });
  await page.goto("/trips/new");
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  const skip = page.getByRole("dialog", { name: "메뉴" }).getByRole("switch", { name: "애니메이션 건너뛰기" });
  await expect(skip).not.toBeChecked();
  await skip.click();
  await expect(skip).toBeChecked();
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("tripilot.web.settings.v1") ?? "{}").skipAnimation)).toBe(true);
  await page.reload();
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "메뉴" }).getByRole("switch", { name: "애니메이션 건너뛰기" })).toBeChecked();
  await page.getByRole("dialog", { name: "메뉴" }).getByRole("switch", { name: "애니메이션 건너뛰기" }).click();
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("tripilot.web.settings.v1") ?? "{}").skipAnimation)).toBe(false);
});

