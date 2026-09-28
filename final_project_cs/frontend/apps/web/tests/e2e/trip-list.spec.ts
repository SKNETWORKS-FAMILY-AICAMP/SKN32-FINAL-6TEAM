import { expect, test, type Page } from "@playwright/test";
import { noHorizontalScroll, submitPlan, useKorean } from "./helpers/app";

/** Demo trips live in this tab's sessionStorage under this prefix (`DEMO_STORAGE_PREFIX`). */
const PREFIX = "tripilot.web-mvp.trip:";

test.beforeEach(async ({ page }) => { await useKorean(page); });

const card = (page: Page) => page.getByRole("region", { name: "내 여행", exact: true });

/** Registers the example plan; the trip is saved once its check starts. Returns the trip id. */
async function addTrip(page: Page) {
  await page.goto("/trips/new");
  await page.getByRole("button", { name: "예시 불러오기" }).click();
  await submitPlan(page);
  return new URL(page.url()).pathname.split("/")[2];
}

/** Copies the first saved trip under new ids, each registered a second later, until the tab holds `total` trips. */
async function fillTrips(page: Page, total: number) {
  await page.evaluate(({ prefix, total }) => {
    const keys = Object.keys(sessionStorage).filter((key) => key.startsWith(prefix));
    const base = JSON.parse(sessionStorage.getItem(keys[0])!);
    for (let index = keys.length; index < total; index += 1) {
      const id = crypto.randomUUID();
      sessionStorage.setItem(prefix + id, JSON.stringify({ ...base, createdAt: base.createdAt + index * 1000, trip: { ...base.trip, id } }));
    }
  }, { prefix: PREFIX, total });
}

const hrefs = (links: ReturnType<Page["locator"]>) => links.evaluateAll((elements) => elements.map((element) => element.getAttribute("href")));

test("첫 화면 내 여행 카드는 0·1·3·4개 이상에 맞춰 최근 3개까지만 보이고, 4개부터 전체일정 보기로 전체 목록을 연다", async ({ page }) => {
  await page.goto("/");
  await expect(card(page).getByText("아직 등록한 여행이 없어요.", { exact: true })).toBeVisible();
  await expect(card(page).getByRole("link")).toHaveCount(0);

  const oldest = await addTrip(page);
  await page.goto("/");
  await expect(card(page).getByRole("listitem")).toHaveCount(1);
  await expect(card(page).getByRole("link", { name: "전체일정 보기" })).toHaveCount(0);
  await expect(card(page).getByRole("listitem")).toContainText("2026-09-15 – 2026-09-16 여행");
  await expect(card(page).getByRole("listitem")).toContainText("등록");

  await fillTrips(page, 3);
  await page.reload();
  await expect(card(page).getByRole("listitem")).toHaveCount(3);
  await expect(card(page).getByRole("link", { name: "전체일정 보기" })).toHaveCount(0);

  await fillTrips(page, 5);
  await page.reload();
  await expect(card(page).getByRole("listitem")).toHaveCount(3);
  const shown = await hrefs(card(page).getByRole("listitem").getByRole("link"));
  expect(shown).not.toContain(`/trips/${oldest}`);
  await card(page).getByRole("link", { name: "전체일정 보기" }).click();
  await expect(page).toHaveURL(/\/trips$/);
  const all = page.locator("#main-content li a");
  await expect(all).toHaveCount(5);
  // The card is the head of the same list, in the same order.
  expect((await hrefs(all)).slice(0, 3)).toEqual(shown);
  await expect(page.getByRole("link", { name: "새 여행 등록", exact: true })).toBeVisible();
});

test("첫 화면 카드·메뉴의 여행 목록 보기·전체 목록이 같은 여행으로 가고, 확인 중인 여행은 진행 단계를 안내한다", async ({ page }) => {
  const id = await addTrip(page);
  await page.goto("/");
  await card(page).getByRole("link", { name: /2026-09-15 – 2026-09-16 여행/ }).click();
  await expect(page).toHaveURL(new RegExp(`/trips/${id}$`));
  await expect(page.getByRole("heading", { name: /여행 계획을 확인하고 있어요|검증 결과를 먼저 확인해 주세요/ })).toBeVisible();

  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await page.getByRole("dialog", { name: "메뉴" }).getByRole("link", { name: "여행 목록 보기" }).click();
  await expect(page).toHaveURL(/\/trips$/);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.locator("#main-content").getByRole("link", { name: /2026-09-15 – 2026-09-16 여행/ }).click();
  await expect(page).toHaveURL(new RegExp(`/trips/${id}$`));
});

test("첫 장에는 등록 버튼과 소개 건너뛰기 없이 아래로 가는 안내만 있고, 마지막 장의 시작 버튼은 약관·취향 설정으로 간다", async ({ page }) => {
  await page.goto("/");
  const hero = page.locator("main > section").first();
  await expect(card(page)).toBeVisible();
  await expect(hero.getByRole("button", { name: /소개 건너뛰기/ })).toHaveCount(0);
  await expect(hero.getByRole("link", { name: /새 여행 등록|여행 계획 등록|내 일정 시작하기/ })).toHaveCount(0);
  await expect(hero.getByRole("button", { name: /새 여행 등록|여행 계획 등록|내 일정 시작하기/ })).toHaveCount(0);
  await hero.getByRole("button", { name: "다음 화면" }).click();
  await expect(page.locator("#how-title")).toBeInViewport();
  await page.locator("main > section").nth(1).getByRole("button", { name: "다음 화면" }).click();
  await expect(page.locator("#start-title")).toBeInViewport();
  await page.getByRole("button", { name: "내 일정 시작하기" }).click();
  await expect(page).toHaveURL(/\/start$/);
});

test("모든 로고는 홈 첫 장으로 돌아오고, 여정 화면 헤더에는 로고와 메뉴만 있다", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "3. 일정 시작" }).click();
  await expect(page.locator("#start-title")).toBeInViewport();
  await page.getByRole("button", { name: "triPilot — 소개 화면으로 돌아가기" }).click();
  await expect(page.locator("#intro-title")).toBeInViewport();

  await page.goto("/start");
  await page.getByRole("link", { name: "triPilot — 소개 화면으로 돌아가기" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.locator("#intro-title")).toBeInViewport();

  for (const path of ["/trips/new", "/trips"]) {
    await page.goto(path);
    const banner = page.getByRole("banner");
    await expect(banner.getByRole("link")).toHaveCount(1);
    await expect(banner.getByRole("button")).toHaveCount(1);
    await banner.getByRole("link", { name: "triPilot 홈으로" }).click();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.locator("#intro-title")).toBeInViewport();
  }
});

test("등록하고 로고로 돌아오면 첫 화면 카드와 전체 목록이 새 여행을 다시 읽는다", async ({ page }) => {
  await page.goto("/");
  await expect(card(page).getByText("아직 등록한 여행이 없어요.", { exact: true })).toBeVisible();
  // Everything below moves inside the app, so the list cached as empty above is what must be refreshed.
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await page.getByRole("dialog", { name: "메뉴" }).getByRole("link", { name: "여행 목록 보기" }).click();
  await expect(page.getByText("아직 등록한 여행이 없어요.", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "새 여행 등록", exact: true }).click();
  await page.getByRole("button", { name: "예시 불러오기" }).click();
  await submitPlan(page);
  await page.getByRole("banner").getByRole("link", { name: "triPilot 홈으로" }).click();
  await expect(card(page).getByRole("listitem")).toHaveCount(1);
  await expect(card(page).getByText("아직 등록한 여행이 없어요.")).toHaveCount(0);
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await page.getByRole("dialog", { name: "메뉴" }).getByRole("link", { name: "여행 목록 보기" }).click();
  await expect(page.locator("#main-content li")).toHaveCount(1);
});

test("목록을 읽지 못하면 첫 화면 카드 안에만 오류와 다시 불러오기를 보이고, 빈 목록으로 숨기지 않는다", async ({ page }) => {
  await page.goto("/");
  await page.evaluate((prefix) => sessionStorage.setItem(prefix + crypto.randomUUID(), "{broken"), PREFIX);
  await page.reload();
  await expect(card(page).getByRole("alert")).toContainText("저장된 여행 데이터를 읽을 수 없어요");
  await expect(card(page).getByText("아직 등록한 여행이 없어요.")).toHaveCount(0);
  await expect(page.locator("#intro-title")).toBeVisible();
  await expect(page.getByRole("button", { name: /LANGUAGE/ })).toBeVisible();

  await page.evaluate((prefix) => Object.keys(sessionStorage).filter((key) => key.startsWith(prefix)).forEach((key) => sessionStorage.removeItem(key)), PREFIX);
  await card(page).getByRole("button", { name: "다시 불러오기" }).click();
  await expect(card(page).getByText("아직 등록한 여행이 없어요.", { exact: true })).toBeVisible();
  await expect(card(page).getByRole("alert")).toHaveCount(0);
});

test("메뉴의 여행 목록 보기는 Tab 순환에 들어가고, Esc로 닫으면 메뉴 버튼으로 돌아오며, 목록 페이지에서 눌러도 메뉴가 닫힌다", async ({ page }) => {
  await page.goto("/trips/new");
  const open = page.getByRole("button", { name: "메뉴", exact: true });
  await open.click();
  const menu = page.getByRole("dialog", { name: "메뉴" });
  const link = menu.getByRole("link", { name: "여행 목록 보기" });
  const close = menu.getByRole("button", { name: "메뉴 닫기" });
  await expect(menu.getByRole("radio", { name: "한국어" })).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(link).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(close).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(menu.getByRole("radio", { name: /고정 하단 탭/ })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(close).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(link).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(menu).toHaveCount(0);
  await expect(open).toBeFocused();

  await open.click();
  await page.keyboard.press("Shift+Tab");
  await expect(link).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/trips$/);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await open.click();
  await link.click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page).toHaveURL(/\/trips$/);
});

test("영어와 PC 기기 틀·375px·320px·낮은 화면에서 첫 화면 카드가 잘리거나 겹치지 않는다", async ({ page }) => {
  await addTrip(page);
  await fillTrips(page, 4);
  const sizes: [number, number, boolean][] = [[1280, 900, true], [375, 812, true], [375, 667, false], [320, 640, false]];
  for (const english of [false, true]) {
    if (english) {
      await page.goto("/");
      await page.getByRole("button", { name: "메뉴", exact: true }).click();
      await page.getByRole("dialog", { name: "메뉴" }).getByText("English").click();
      await page.keyboard.press("Escape");
      const recent = page.getByRole("region", { name: "My trips", exact: true });
      await expect(recent.getByRole("link", { name: /View all/ })).toBeVisible();
      await expect(recent.getByRole("listitem").first()).toContainText("Trip · 2026-09-15 – 2026-09-16");
      await expect(recent.getByRole("listitem").first()).toContainText("Added");
      await page.getByRole("button", { name: "Menu", exact: true }).click();
      await expect(page.getByRole("dialog", { name: "Menu" }).getByRole("link", { name: "View trip list" })).toBeVisible();
      await page.keyboard.press("Escape");
    }
    for (const [width, height, together] of sizes) {
      await page.setViewportSize({ width, height });
      await page.goto("/");
      await expect(page.locator("section:has(#recent-trips-title) li")).toHaveCount(3);
      await noHorizontalScroll(page);
      const { fitsFirst, ...scrolled } = await page.locator("main > section").first().evaluate((hero) => {
        const box = (element: Element | null | undefined) => element!.getBoundingClientRect();
        const view = box(hero);
        const lastRow = () => box(hero.querySelector("li:last-child"));
        // Before scrolling: the introduction and all three trips on one screen.
        const fitsFirst = box(hero.querySelector("#intro-title")).top >= view.top && lastRow().bottom <= view.bottom;
        // Scrolled to the end: nothing is cut off, and the card, the badge and the way down do not overlap.
        hero.scrollTop = hero.scrollHeight;
        const card = box(hero.querySelector("#recent-trips-title")!.closest("section"));
        const badge = box([...hero.querySelectorAll("small")].find((small) => small.textContent === "A LITTLE MORE YOU")?.parentElement);
        const down = box(hero.querySelector('button[aria-label="다음 화면"], button[aria-label="Next screen"]'));
        return { fitsFirst, rowInCard: lastRow().bottom <= card.bottom + .5, ordered: card.bottom <= badge.top && badge.bottom <= down.top, downInView: down.bottom <= view.bottom + .5 };
      });
      const label = `${english ? "en" : "ko"} ${width}x${height}`;
      if (together) expect(fitsFirst, label).toBe(true);
      expect(scrolled, label).toEqual({ rowInCard: true, ordered: true, downInView: true });
    }
  }
});
