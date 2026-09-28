import { expect, test, type Page } from "@playwright/test";
import { agreeTerms, noHorizontalScroll, openCompletedResults, pickMenuLanguage, startTrip, submitPlan, useKorean } from "./helpers/app";

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

/** The full list's rows, the trip ids in the order it shows them, and the ids stored in this tab. */
const rows = (page: Page) => page.locator("#main-content li");
const shownIds = async (page: Page) => (await hrefs(page.locator("#main-content li a"))).map((href) => href!.split("/")[2]);
const stored = (page: Page) => page.evaluate((prefix) => Object.keys(sessionStorage).filter((key) => key.startsWith(prefix)).map((key) => key.slice(prefix.length)).sort(), PREFIX);
const confirmDialog = (page: Page) => page.getByRole("alertdialog");
const said = (page: Page) => page.locator("#main-content").getByRole("status");
const warned = (page: Page) => page.locator("#main-content").getByRole("alert");

/** Makes removing one trip's record fail in this tab, as a full or locked storage would. */
async function failRemoving(page: Page, id: string) {
  await page.evaluate((key) => {
    const remove = Storage.prototype.removeItem;
    Storage.prototype.removeItem = function (name: string) {
      if (name === key) throw new Error("denied");
      return remove.call(this, name);
    };
  }, PREFIX + id);
}

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

test("영어와 PC 기기 틀·375px·320px·낮은 화면에서 첫 화면 카드가 잘리거나 겹치지 않는다", async ({ page }) => {
  await addTrip(page);
  await fillTrips(page, 4);
  const sizes: [number, number, boolean][] = [[1280, 900, true], [375, 812, true], [375, 667, false], [320, 640, false]];
  for (const english of [false, true]) {
    if (english) {
      await page.goto("/");
      await page.getByRole("button", { name: "메뉴", exact: true }).click();
      await pickMenuLanguage(page, "메뉴", "English");
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

test("휴지통은 상세로 가지 않고 확인창을 열며, 확인창 취소는 아무것도 바꾸지 않고, 삭제는 같은 제목의 여행 중 그 ID 하나만 지운다", async ({ page }) => {
  await addTrip(page);
  await fillTrips(page, 3);
  await page.evaluate(() => sessionStorage.setItem("tripilot.web-mvp.draft", "작성 중인 글"));
  await page.goto("/trips");
  await expect(rows(page)).toHaveCount(3);
  const ids = await shownIds(page);
  // Three copies of one trip: the same title, so the ID alone tells them apart.
  await expect(rows(page).locator("strong")).toHaveText(Array(3).fill("2026-09-15 – 2026-09-16 여행"));
  const trash = rows(page).nth(1).getByRole("button");
  await expect(trash).toHaveAccessibleName(/^2026-09-15 – 2026-09-16 여행\(.+ 등록\) 삭제$/);

  await trash.click();
  await expect(page).toHaveURL(/\/trips$/);
  const dialog = confirmDialog(page);
  await expect(dialog).toHaveAccessibleName("이 여행을 삭제할까요?");
  await expect(dialog).toContainText("2026-09-15 – 2026-09-16 여행");
  await expect(dialog).toContainText("등록");
  await expect(dialog).toContainText("이 탭에 저장된 여행과 대화 기록이 삭제돼요. 삭제한 내용은 되돌릴 수 없어요.");
  await expect(dialog.getByRole("button", { name: "취소" })).toBeFocused();
  await dialog.getByRole("button", { name: "취소" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(trash).toBeFocused();
  expect(await stored(page)).toEqual([...ids].sort());

  await trash.click();
  await confirmDialog(page).getByRole("button", { name: "삭제", exact: true }).click();
  await expect(said(page)).toHaveText("여행 1개를 삭제했어요.");
  await expect(rows(page)).toHaveCount(2);
  expect(await shownIds(page)).toEqual([ids[0], ids[2]]);
  expect(await stored(page)).toEqual([ids[0], ids[2]].sort());
  expect(await page.evaluate(() => [sessionStorage.getItem("tripilot.web-mvp.draft"), JSON.parse(localStorage.getItem("tripilot.web.settings.v1")!).language])).toEqual(["작성 중인 글", "ko"]);
  await expect(page.getByRole("button", { name: "선택 삭제" })).toBeFocused();
});

test("선택 삭제는 체크박스로 고르는 모드로 바꾸고, 0개면 삭제가 꺼지며, 행을 눌러도 상세로 가지 않고, 확인창 취소는 선택을 지키고 상단 취소는 모드를 끝낸다", async ({ page }) => {
  await addTrip(page);
  await fillTrips(page, 3);
  await page.goto("/trips");
  const ids = await shownIds(page);
  await page.getByRole("button", { name: "선택 삭제" }).click();
  const remove = page.getByRole("button", { name: /^삭제 \(\d+\)$/ });
  const boxes = page.getByRole("checkbox");
  await expect(page.getByRole("button", { name: "취소", exact: true })).toBeFocused();
  await expect(remove).toHaveText("삭제 (0)");
  await expect(remove).toBeDisabled();
  await expect(boxes).toHaveCount(3);
  for (const box of await boxes.all()) await expect(box).not.toBeChecked();
  // No arrows, no bins, no links to open, and no new-trip button while picking.
  await expect(rows(page).locator("a, button")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "새 여행 등록" })).toHaveCount(0);

  // The whole row picks and unpicks, and opens nothing.
  await rows(page).nth(0).getByText("2026-09-15 – 2026-09-16 여행").click();
  await expect(page).toHaveURL(/\/trips$/);
  await expect(boxes.nth(0)).toBeChecked();
  await boxes.nth(2).check();
  await expect(remove).toHaveText("삭제 (2)");
  await expect(remove).toBeEnabled();
  await rows(page).nth(0).click();
  await expect(boxes.nth(0)).not.toBeChecked();
  await expect(remove).toHaveText("삭제 (1)");
  await rows(page).nth(0).click();

  await remove.click();
  const dialog = confirmDialog(page);
  await expect(dialog).toHaveAccessibleName("선택한 여행 2개를 삭제할까요?");
  await expect(dialog).toContainText("선택한 여행 2개");
  await expect(dialog.getByRole("button", { name: "2개 삭제" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(remove).toBeFocused();
  await expect(boxes.nth(0)).toBeChecked();
  await expect(boxes.nth(2)).toBeChecked();

  await page.getByRole("button", { name: "취소", exact: true }).click();
  await expect(boxes).toHaveCount(0);
  await expect(page.getByRole("button", { name: "선택 삭제" })).toBeFocused();
  await expect(page.getByRole("link", { name: "새 여행 등록" })).toBeVisible();
  expect(await stored(page)).toEqual([...ids].sort());
  // Coming back starts with nothing picked.
  await page.getByRole("button", { name: "선택 삭제" }).click();
  for (const box of await boxes.all()) await expect(box).not.toBeChecked();
});

test("고른 여행은 확인창 한 번으로 지우고, 확인창 안에서 초점이 돌며 배경은 눌리지 않고, 두 번 눌러도 한 번만 지운다", async ({ page }) => {
  await addTrip(page);
  await fillTrips(page, 4);
  await page.goto("/trips");
  const ids = await shownIds(page);
  await page.getByRole("button", { name: "선택 삭제" }).click();
  await page.getByRole("checkbox").nth(1).check();
  await page.getByRole("checkbox").nth(3).check();
  await page.getByRole("button", { name: "삭제 (2)" }).click();
  const dialog = confirmDialog(page), cancel = dialog.getByRole("button", { name: "취소" }), confirm = dialog.getByRole("button", { name: "2개 삭제" });
  await expect(cancel).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(confirm).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(cancel).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(confirm).toBeFocused();
  await page.mouse.click(4, 4);
  await expect(dialog).toBeVisible();
  expect(await stored(page)).toEqual([...ids].sort());

  // A double press: the dialog stays on `삭제 중…` and takes the second click, so the list beneath opens nothing and
  // nothing is deleted twice (a second delete of the same trips would fail and say so).
  await confirm.dblclick();
  await expect(dialog.getByRole("button", { name: "삭제 중…" })).toBeVisible();
  await expect(said(page)).toHaveText("여행 2개를 삭제했어요.");
  await expect(page).toHaveURL(/\/trips$/);
  await expect(warned(page)).toHaveText("");
  await expect(page.getByRole("checkbox")).toHaveCount(0);
  expect(await shownIds(page)).toEqual([ids[0], ids[2]]);
  expect(await stored(page)).toEqual([ids[0], ids[2]].sort());
  await expect(page.getByRole("button", { name: "선택 삭제" })).toBeFocused();
});

test("일부만 지워지면 지워진 것만 빠지고 실패한 여행은 선택된 채 남으며, 한 건 삭제가 실패하면 행이 그대로 남는다", async ({ page }) => {
  await addTrip(page);
  await fillTrips(page, 3);
  await page.goto("/trips");
  const ids = await shownIds(page);
  await failRemoving(page, ids[1]);

  await page.getByRole("button", { name: "선택 삭제" }).click();
  for (const box of await page.getByRole("checkbox").all()) await box.check();
  await page.getByRole("button", { name: "삭제 (3)" }).click();
  await confirmDialog(page).getByRole("button", { name: "3개 삭제" }).click();
  await expect(warned(page)).toHaveText("2개 삭제, 1개 삭제 실패. 다시 시도해 주세요.");
  await expect(said(page)).toHaveText("");
  await expect(page.getByRole("checkbox")).toHaveCount(1);
  await expect(page.getByRole("checkbox")).toBeChecked();
  await expect(page.getByRole("button", { name: "삭제 (1)" })).toBeFocused();
  expect(await stored(page)).toEqual([ids[1]]);

  await page.getByRole("button", { name: "취소", exact: true }).click();
  const trash = rows(page).first().getByRole("button");
  await trash.click();
  await confirmDialog(page).getByRole("button", { name: "삭제", exact: true }).click();
  await expect(warned(page)).toHaveText("삭제하지 못했어요. 다시 시도해 주세요.");
  await expect(rows(page)).toHaveCount(1);
  await expect(trash).toBeFocused();
  expect(await shownIds(page)).toEqual([ids[1]]);
});

test("마지막 여행을 지우면 빈 목록과 새 여행 등록만 남고, 지운 여행 주소·첫 화면 카드·온보딩 이어보기·새로고침이 모두 삭제를 따른다", async ({ page }) => {
  // Onboarding, then a trip taken to management: it becomes the onboarding's active trip.
  await page.goto("/start");
  await page.getByRole("button", { name: /약관 동의/ }).click();
  await agreeTerms(page);
  await page.getByRole("button", { name: "시작하기" }).click();
  for (let at = 0; at < 6; at += 1) {
    await expect(page.locator(`#question-title-${at}`)).toBeFocused();
    await page.getByRole("button", { name: "응답하지 않고 넘어가기" }).click();
  }
  await page.getByRole("button", { name: "여행 계획 등록하기" }).click();
  await page.getByRole("button", { name: "예시 불러오기" }).click();
  await submitPlan(page);
  await openCompletedResults(page);
  await startTrip(page);
  const id = new URL(page.url()).pathname.split("/")[2];
  // Read it in English too, so the trip is cached in both languages.
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await pickMenuLanguage(page, "메뉴", "English");
  await expect(page.getByRole("dialog", { name: "Menu" })).toBeVisible();
  await pickMenuLanguage(page, "Menu", "한국어");
  await page.getByRole("dialog", { name: "메뉴" }).getByRole("link", { name: "여행 목록 보기" }).click();
  await expect(page).toHaveURL(/\/trips$/);

  await rows(page).first().getByRole("button").click();
  await confirmDialog(page).getByRole("button", { name: "삭제", exact: true }).click();
  await expect(said(page)).toHaveText("여행 1개를 삭제했어요.");
  await expect(page.locator("#main-content").getByText("아직 등록한 여행이 없어요.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "선택 삭제" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "새 여행 등록" })).toBeFocused();
  expect(await stored(page)).toEqual([]);

  // Back to the deleted trip's page inside the app: nothing cached shows it.
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`/trips/${id}$`));
  await expect(page.getByText(/이 탭에 저장된 여행을 찾을 수 없어요/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "나의 여행", exact: true })).toHaveCount(0);

  // Home and onboarding follow: no recent trip, and the summary no longer continues the deleted trip.
  await page.getByRole("banner").getByRole("link", { name: "triPilot 홈으로" }).click();
  await expect(card(page).getByText("아직 등록한 여행이 없어요.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "3. 일정 시작" }).click();
  await page.getByRole("button", { name: "내 일정 시작하기" }).click();
  const preferences = page.getByRole("button", { name: /여행 취향 알아보기/ }).first();
  if (await preferences.getAttribute("aria-expanded") !== "true") await preferences.click();
  await expect(page.getByRole("button", { name: "여행 계획 등록하기" })).toBeVisible();
  await expect(page.getByRole("button", { name: "내 여행 이어보기" })).toHaveCount(0);

  // A reload does not bring it back.
  await page.goto(`/trips/${id}`);
  await expect(page.getByText(/이 탭에 저장된 여행을 찾을 수 없어요/)).toBeVisible();
  await page.goto("/trips");
  await expect(page.locator("#main-content").getByText("아직 등록한 여행이 없어요.", { exact: true })).toBeVisible();
});

test("영어·키보드로 한 건 삭제와 선택 삭제를 쓰고, PC 기기 틀·375px·320px에서 제목·버튼·행이 겹치거나 넘치지 않는다", async ({ page }) => {
  await addTrip(page);
  await fillTrips(page, 3);
  await page.goto("/trips");
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await pickMenuLanguage(page, "메뉴", "English");
  await page.keyboard.press("Escape");
  const trash = rows(page).first().getByRole("button");
  await expect(trash).toHaveAccessibleName(/^Delete Trip · 2026-09-15 – 2026-09-16 \(added .+\)$/);

  // Enter opens the dialog, Escape returns to the bin, Tab reaches Delete, Enter deletes.
  await trash.focus();
  await page.keyboard.press("Enter");
  const dialog = confirmDialog(page);
  await expect(dialog).toHaveAccessibleName("Delete this trip?");
  await expect(dialog).toContainText("The trip and its chat saved in this tab will be deleted. This can’t be undone.");
  await page.keyboard.press("Escape");
  await expect(trash).toBeFocused();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Tab");
  await expect(dialog.getByRole("button", { name: "Delete", exact: true })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(said(page)).toHaveText("Deleted 1 trip.");
  await expect(rows(page)).toHaveCount(2);

  // Select mode: Tab skips the switched-off Delete (0) to the first checkbox; Space picks.
  const select = page.getByRole("button", { name: "Select to delete" });
  await expect(select).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: "Cancel", exact: true })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("checkbox").first()).toBeFocused();
  await page.keyboard.press("Space");
  await expect(page.getByRole("button", { name: "Delete (1)" })).toBeEnabled();

  /** Nothing in the title row overlaps the title, and every row's parts sit side by side inside the row. */
  const fits = () => page.locator("#main-content").evaluate((main) => {
    const box = (element: Element) => element.getBoundingClientRect();
    const title = box(main.querySelector("header h1")!);
    const clear = [...main.querySelectorAll("header button")].every((button) => box(button).left >= title.right - .5 || box(button).top >= title.bottom - .5);
    const inRows = [...main.querySelectorAll("li")].every((row) => {
      // A row's own parts, left to right: checkbox and text in select mode; text, arrow and bin otherwise.
      const parts = [...row.querySelectorAll(":scope > label > input, :scope > label > span, :scope > a > span, :scope > a > svg, :scope > button")];
      const ordered = parts.every((part, index) => index === 0 || box(parts[index - 1]).right <= box(part).left + .5);
      return ordered && parts.every((part) => box(part).right <= box(row).right + .5);
    });
    return { clear, inRows };
  });
  for (const selecting of [true, false]) {
    if (!selecting) await page.getByRole("button", { name: "Cancel", exact: true }).click();
    for (const [width, height] of [[1280, 900], [375, 812], [320, 640]]) {
      await page.setViewportSize({ width, height });
      await noHorizontalScroll(page);
      expect(await fits(), `${selecting ? "select" : "list"} ${width}x${height}`).toEqual({ clear: true, inRows: true });
    }
  }
});
