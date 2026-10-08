import { expect, test, type Locator, type Page } from "@playwright/test";
import { KEY_STORAGE, TRIP_ID, hydrated, mockServer, noHorizontalScroll, pickMenuLanguage, registerStubTrip, start, checkPlan, tripScreen } from "./helpers";

/**
 * 여행 목록(첫 화면의 「내 여행」 카드 · `/trips`)과 여행 삭제 — 테스트용 모방 서버로 도는 자동 시험(실제 서버 아님).
 * 옛 데모 화면 시험(`tests/e2e/trip-list.spec.ts`, 탭 저장소 기준)을 서버 기준으로 옮긴 것이다.
 *
 * ★목록은 서버(`GET /v1/web/trips`)가 주고, 삭제는 `POST /v1/web/trips/{id}/delete` 로 요청한다. 이 삭제 호출은 실서버에 아직 없다
 *   (백엔드에 요청한 계약) — 모방 서버가 그 계약대로 흉내 낸다. 그러니 「지워졌나」는 저장소가 아니라 세 가지로 본다:
 *   화면의 목록, 서버가 받은 삭제 요청(어느 id 를 몇 번), 새로고침한 뒤의 목록.
 * ★모방 서버의 여행은 모두 제목이 「내 여행」이고, 등록 시각이 1분씩 달라 최신순이다. 첫째가 `TRIP_ID`, 나머지는 번호가 올라간다.
 */

test.beforeEach(async ({ page, request }) => {
  await mockServer(request).reset();
  await start(page);
});

/** 모방 서버가 목록에 올리는 i 번째 여행의 id (`stub-server.mjs` 의 `rowId`) — 0 번째가 가장 최근. */
const tripAt = (index: number) => index === 0 ? TRIP_ID : `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`;
const listed = (count: number) => Array.from({ length: count }, (_, index) => tripAt(index));

const card = (page: Page) => page.getByRole("region", { name: "내 여행", exact: true });
const hrefs = (links: Locator) => links.evaluateAll((elements) => elements.map((element) => element.getAttribute("href")));

/** 전체 목록의 행, 목록이 보이는 순서대로의 여행 id. ★선택 삭제 모드에서는 행에 링크가 없어 `shownIds` 가 빈다 — 그때는 행 개수로 본다. */
const rows = (page: Page) => page.locator("#main-content li");
const shownIds = async (page: Page) => (await hrefs(page.locator("#main-content li a"))).map((href) => href!.split("/")[2]);
const confirmDialog = (page: Page) => page.getByRole("alertdialog");
const said = (page: Page) => page.locator("#main-content").getByRole("status");
const warned = (page: Page) => page.locator("#main-content").getByRole("alert");

/** 서버가 받은 삭제 요청의 여행 id 들(`POST /v1/web/trips/{id}/delete`), 온 순서대로. 한꺼번에 보낸 요청의 순서는 믿지 않는다 — 비교할 때 정렬한다. */
const asked = async (server: ReturnType<typeof mockServer>) => (await server.received("POST", "/delete")).map((entry) => entry.path.split("/").at(-2)!);

/** 삭제 요청에 서버가 돌려준 상태 번호들(브라우저가 받은 그대로). 요청을 보내기 전에 걸어 둔다. */
function watchDeletes(page: Page) {
  const statuses: number[] = [];
  page.on("response", (response) => { if (response.request().method() === "POST" && response.url().endsWith("/delete")) statuses.push(response.status()); });
  return statuses;
}

const openMenu = (page: Page, name: "메뉴" | "Menu") => page.getByRole("button", { name, exact: true }).first().click();
const menuLink = (page: Page, menu: "메뉴" | "Menu", link: string | RegExp) => page.getByRole("dialog", { name: menu }).getByRole("link", { name: link });

test("첫 화면 내 여행 카드는 0·1·3·4개 이상에 맞춰 최근 3개까지만 보이고, 4개부터 전체일정 보기로 전체 목록을 연다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ trips: "none" });
  await page.goto("/");
  await expect(card(page).getByText("아직 등록한 여행이 없어요.", { exact: true })).toBeVisible();
  await expect(card(page).getByRole("link")).toHaveCount(0);

  await server.scenario({ trips: 1 });
  await page.reload();
  await expect(card(page).getByRole("listitem")).toHaveCount(1);
  await expect(card(page).getByRole("link", { name: "전체일정 보기" })).toHaveCount(0);
  await expect(card(page).getByText("아직 등록한 여행이 없어요.")).toHaveCount(0);
  await expect(card(page).getByRole("listitem")).toContainText("내 여행");
  await expect(card(page).getByRole("listitem")).toContainText("등록");

  await server.scenario({ trips: 3 });
  await page.reload();
  await expect(card(page).getByRole("listitem")).toHaveCount(3);
  await expect(card(page).getByRole("link", { name: "전체일정 보기" })).toHaveCount(0);

  await server.scenario({ trips: 5 });
  await page.reload();
  await expect(card(page).getByRole("listitem")).toHaveCount(3);
  const shown = await hrefs(card(page).getByRole("listitem").getByRole("link"));
  await card(page).getByRole("link", { name: "전체일정 보기" }).click();
  await expect(page).toHaveURL(/\/trips$/);
  const all = page.locator("#main-content li a");
  await expect(all).toHaveCount(5);
  const ordered = await hrefs(all);
  // 카드는 같은 목록의 머리 — 같은 순서(서버가 준 최신순)이고, 가장 오래된 여행은 카드에 없다.
  expect(ordered).toEqual(listed(5).map((id) => `/trips/${id}`));
  expect(ordered.slice(0, 3)).toEqual(shown);
  expect(shown).not.toContain(ordered[4]);
  await expect(page.getByRole("link", { name: "새 여행 등록", exact: true })).toBeVisible();
});

test("첫 화면 카드·메뉴의 여행 목록 보기·전체 목록이 같은 여행으로 가고, 여행 화면은 그 여행을 연다", async ({ page }) => {
  await page.goto("/");
  await card(page).getByRole("link", { name: /^내 여행/ }).click();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));
  await expect(tripScreen(page)).toBeVisible();

  await openMenu(page, "메뉴");
  await menuLink(page, "메뉴", "여행 목록 보기").click();
  await expect(page).toHaveURL(/\/trips$/);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.locator("#main-content").getByRole("link", { name: /^내 여행/ }).click();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));
  await expect(tripScreen(page)).toBeVisible();
});

test("첫 장에는 등록 버튼과 소개 건너뛰기 없이 아래로 가는 안내만 있고, 마지막 장의 시작 버튼은 약관·취향 설정으로 간다", async ({ page }) => {
  await page.addInitScript(() => localStorage.removeItem("tripilot.web.consent.v1"));      // 약관에 아직 동의하지 않은 사람(앞서 심은 동의 사본을 지운다)
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
    await banner.getByRole("link", { name: "triPilot — 소개 화면으로 돌아가기" }).click();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.locator("#intro-title")).toBeInViewport();
  }
});

test("등록하고 로고로 돌아오면 첫 화면 카드와 전체 목록이 새 여행을 다시 읽는다", async ({ page, request }) => {
  await mockServer(request).scenario({ trips: "none" });
  await page.goto("/");
  await expect(card(page).getByText("아직 등록한 여행이 없어요.", { exact: true })).toBeVisible();
  // 아래는 모두 앱 안에서 옮겨 다닌다(주소창으로 새로 열면 캐시가 사라진다) — 위에서 「비었다」고 읽어 둔 목록이 새로 읽혀야 한다.
  await openMenu(page, "메뉴");
  await menuLink(page, "메뉴", "여행 목록 보기").click();
  await expect(page.locator("#main-content").getByText("아직 등록한 여행이 없어요.", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "새 여행 등록", exact: true }).click();
  // `registerStubTrip` 은 주소창으로 열기 때문에 쓰지 않는다 — 같은 순서를 앱 안에서 밟는다.
  await expect(page).toHaveURL(/\/trips\/new$/);
  await hydrated(page);
  await page.getByLabel("나의 여행 계획").fill("10/1 09:00 경복궁 관람");
  await checkPlan(page);
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);
  await page.getByRole("button", { name: "여행 등록" }).click();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));
  await page.getByRole("banner").getByRole("link", { name: "triPilot — 소개 화면으로 돌아가기" }).click();
  await expect(card(page).getByRole("listitem")).toHaveCount(1);
  await expect(card(page).getByText("아직 등록한 여행이 없어요.")).toHaveCount(0);
  await openMenu(page, "메뉴");
  await menuLink(page, "메뉴", "여행 목록 보기").click();
  await expect(rows(page)).toHaveCount(1);
});

test("목록을 읽지 못하면(서버 500) 첫 화면 카드 안에만 오류와 다시 불러오기를 보이고, 빈 목록으로 숨기지 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ fail: "trips" });
  await page.goto("/");
  await expect(card(page).getByRole("alert")).toContainText("서버 오류");
  await expect(card(page).getByText("아직 등록한 여행이 없어요.")).toHaveCount(0);
  await expect(page.locator("#intro-title")).toBeVisible();

  await server.scenario({ fail: "", trips: "none" });
  await card(page).getByRole("button", { name: "다시 불러오기" }).click();
  await expect(card(page).getByText("아직 등록한 여행이 없어요.", { exact: true })).toBeVisible();
  await expect(card(page).getByRole("alert")).toHaveCount(0);

  // 전체 목록도 같다: 못 읽었다고 말하고(빈 목록 문구가 아니다), 다시 불러오면 읽는다.
  await server.scenario({ fail: "trips" });
  await page.goto("/trips");
  await expect(page.getByRole("heading", { name: "여행 정보를 불러오지 못했어요" })).toBeVisible();
  await expect(page.locator("#main-content").getByRole("alert")).toHaveText("서버 오류");
  await expect(page.getByText("아직 등록한 여행이 없어요.")).toHaveCount(0);
  await server.scenario({ fail: "" });
  await page.getByRole("button", { name: "다시 불러오기" }).click();
  await expect(page.locator("#main-content").getByText("아직 등록한 여행이 없어요.", { exact: true })).toBeVisible();
});

test("영어와 PC 기기 틀·375px·320px·낮은 화면에서 첫 화면 카드가 잘리거나 겹치지 않는다", async ({ page, request }) => {
  await mockServer(request).scenario({ trips: 4 });
  const sizes: [number, number, boolean][] = [[1280, 900, true], [375, 812, true], [375, 667, false], [320, 640, false]];
  for (const english of [false, true]) {
    if (english) {
      await page.goto("/");
      await openMenu(page, "메뉴");
      await pickMenuLanguage(page, "메뉴", "English");
      await page.keyboard.press("Escape");
      const recent = page.getByRole("region", { name: "My trips", exact: true });
      await expect(recent.getByRole("link", { name: /View all/ })).toBeVisible();
      // 제목은 서버가 준 그대로라 영어로 바뀌지 않는다 — 바뀌는 것은 「등록」 문구다.
      await expect(recent.getByRole("listitem").first()).toContainText("내 여행");
      await expect(recent.getByRole("listitem").first()).toContainText("Added");
      await openMenu(page, "Menu");
      await expect(menuLink(page, "Menu", "View trip list")).toBeVisible();
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
        // 스크롤 전: 소개와 여행 3개가 한 화면에 들어온다.
        const fitsFirst = box(hero.querySelector("#intro-title")).top >= view.top && lastRow().bottom <= view.bottom;
        // 끝까지 스크롤: 잘린 곳이 없고, 카드·배지·아래 화살표가 겹치지 않는다.
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

test("휴지통은 상세로 가지 않고 확인창을 열며, 확인창 취소는 아무것도 바꾸지 않고, 삭제는 같은 제목의 여행 중 그 ID 하나만 지운다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ trips: 3 });
  await page.goto("/trips");
  await expect(rows(page)).toHaveCount(3);
  const ids = await shownIds(page);
  expect(ids).toEqual(listed(3));
  // 같은 제목이 셋: 제목으로는 가를 수 없고, 어느 것을 지우는지는 id 가 정한다.
  await expect(rows(page).locator("strong")).toHaveText(Array(3).fill("내 여행"));
  const trash = rows(page).nth(1).getByRole("button");
  await expect(trash).toHaveAccessibleName(/^내 여행\(.+ 등록\) 삭제$/);

  await trash.click();
  await expect(page).toHaveURL(/\/trips$/);
  const dialog = confirmDialog(page);
  await expect(dialog).toHaveAccessibleName("이 여행을 삭제할까요?");
  await expect(dialog).toContainText("내 여행");
  await expect(dialog).toContainText("등록");
  await expect(dialog).toContainText("서버에 저장된 이 여행과 대화 기록, 여행계획서 링크가 삭제되고 알림도 멈춰요. 삭제한 내용은 되돌릴 수 없어요.");
  await expect(dialog.getByRole("button", { name: "취소" })).toBeFocused();
  await dialog.getByRole("button", { name: "취소" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(trash).toBeFocused();
  // 취소했으니 서버에는 아무 요청도 가지 않았고 목록도 그대로다.
  expect(await asked(server)).toEqual([]);
  expect(await shownIds(page)).toEqual(ids);

  await trash.click();
  await confirmDialog(page).getByRole("button", { name: "삭제", exact: true }).click();
  await expect(said(page)).toHaveText("여행 1개를 삭제했어요.");
  await expect(rows(page)).toHaveCount(2);
  expect(await shownIds(page)).toEqual([ids[0], ids[2]]);
  // 서버에는 가운데 여행의 id 로 딱 한 번 요청이 갔고, 새로고침해도 그대로다(서버가 정말 지웠다).
  expect(await asked(server)).toEqual([ids[1]]);
  expect(await page.evaluate((key) => [localStorage.getItem(key), JSON.parse(localStorage.getItem("tripilot.web.settings.v1")!).language], KEY_STORAGE)).toEqual([null, "ko"]);   // 키는 저장소에 없다 — 세션은 쿠키다
  await expect(page.getByRole("button", { name: "선택 삭제" })).toBeFocused();
  await page.reload();
  await expect(rows(page)).toHaveCount(2);
  expect(await shownIds(page)).toEqual([ids[0], ids[2]]);
});

test("선택 삭제는 체크박스로 고르는 모드로 바꾸고, 0개면 삭제가 꺼지며, 행을 눌러도 상세로 가지 않고, 확인창 취소는 선택을 지키고 상단 취소는 모드를 끝낸다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ trips: 3 });
  await page.goto("/trips");
  await expect(rows(page)).toHaveCount(3);
  const ids = await shownIds(page);
  await page.getByRole("button", { name: "선택 삭제" }).click();
  const remove = page.getByRole("button", { name: /^삭제 \(\d+\)$/ });
  const boxes = page.getByRole("checkbox");
  await expect(page.getByRole("button", { name: "취소", exact: true })).toBeFocused();
  await expect(remove).toHaveText("삭제 (0)");
  await expect(remove).toBeDisabled();
  await expect(boxes).toHaveCount(3);
  for (const box of await boxes.all()) await expect(box).not.toBeChecked();
  // 고르는 동안에는 화살표도 휴지통도 열리는 링크도 새 여행 등록 단추도 없다.
  await expect(rows(page).locator("a, button")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "새 여행 등록" })).toHaveCount(0);

  // 행 전체가 고르고 푸는 자리이고, 아무것도 열지 않는다.
  await rows(page).nth(0).getByText("내 여행", { exact: true }).click();
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
  expect(await shownIds(page)).toEqual(ids);
  expect(await asked(server)).toEqual([]);
  // 돌아오면 아무것도 고르지 않은 채로 시작한다.
  await page.getByRole("button", { name: "선택 삭제" }).click();
  for (const box of await boxes.all()) await expect(box).not.toBeChecked();
});

test("고른 여행은 확인창 한 번으로 지우고, 확인창 안에서 초점이 돌며 배경은 눌리지 않고, 두 번 눌러도 한 번만 지운다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ trips: 4 });
  await page.goto("/trips");
  await expect(rows(page)).toHaveCount(4);
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
  expect(await asked(server)).toEqual([]);

  // 두 번 누름: 확인창이 `삭제 중…` 으로 남아 두 번째 누름을 받으니, 밑의 목록은 아무것도 열지 않고
  // 같은 여행을 두 번 지우라는 요청도 가지 않는다(서버에 간 삭제 요청이 정확히 둘 — 여행마다 하나).
  await confirm.dblclick();
  await expect(dialog.getByRole("button", { name: "삭제 중…" })).toBeVisible();
  await expect(said(page)).toHaveText("여행 2개를 삭제했어요.");
  await expect(page).toHaveURL(/\/trips$/);
  await expect(warned(page)).toHaveText("");
  await expect(page.getByRole("checkbox")).toHaveCount(0);
  await expect(rows(page)).toHaveCount(2);
  expect(await shownIds(page)).toEqual([ids[0], ids[2]]);
  expect([...await asked(server)].sort()).toEqual([ids[1], ids[3]].sort());
  await expect(page.getByRole("button", { name: "선택 삭제" })).toBeFocused();
});

test("일부만 지워지면 지워진 것만 빠지고 실패한 여행은 선택된 채 남으며, 한 건 삭제가 실패하면 행이 그대로 남는다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ trips: 3 });
  await page.goto("/trips");
  await expect(rows(page)).toHaveCount(3);
  const ids = await shownIds(page);
  // 가운데 여행만 서버가 500 으로 거절한다(목록을 읽은 뒤에 건다 — 목록 id 는 이때 알려진다).
  await server.scenario({ deleteFails: [ids[1]] });

  await page.getByRole("button", { name: "선택 삭제" }).click();
  for (const box of await page.getByRole("checkbox").all()) await box.check();
  await page.getByRole("button", { name: "삭제 (3)" }).click();
  await confirmDialog(page).getByRole("button", { name: "3개 삭제" }).click();
  await expect(warned(page)).toHaveText("2개 삭제, 1개 삭제 실패. 다시 시도해 주세요.");
  await expect(said(page)).toHaveText("");
  await expect(page.getByRole("checkbox")).toHaveCount(1);
  await expect(page.getByRole("checkbox")).toBeChecked();
  await expect(rows(page)).toHaveCount(1);
  await expect(page.getByRole("button", { name: "삭제 (1)" })).toBeFocused();
  // 셋 모두 서버에 요청이 갔고(하나는 거절당했다), 목록에는 거절당한 여행만 남았다.
  expect([...await asked(server)].sort()).toEqual([...ids].sort());

  await page.getByRole("button", { name: "취소", exact: true }).click();
  const trash = rows(page).first().getByRole("button");
  await trash.click();
  await confirmDialog(page).getByRole("button", { name: "삭제", exact: true }).click();
  await expect(warned(page)).toHaveText("삭제하지 못했어요. 다시 시도해 주세요.");
  await expect(rows(page)).toHaveCount(1);
  await expect(trash).toBeFocused();
  expect(await shownIds(page)).toEqual([ids[1]]);
  expect((await asked(server)).filter((id) => id === ids[1])).toHaveLength(2);
  // 새로고침해도 서버가 지킨 여행이 남아 있다.
  await page.reload();
  await expect(rows(page)).toHaveCount(1);
  expect(await shownIds(page)).toEqual([ids[1]]);
});

test("마지막 여행을 지우면 빈 목록과 새 여행 등록만 남고, 지운 여행 주소·첫 화면 카드·새로고침이 모두 삭제를 따른다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ trips: "none" });
  const tripReads = async () => (await server.received("GET", `/v1/web/trips/${TRIP_ID}`)).length;
  // 여행을 등록해 여행 화면까지 간다(이 앱에서 등록은 모방 서버 여행 하나를 목록에 올린다).
  await registerStubTrip(page);
  // 영어로도 읽어, 여행이 두 언어로 캐시에 들어 있게 한다 — 삭제는 둘 다 지워야 한다.
  const before = await tripReads();
  await openMenu(page, "메뉴");
  await pickMenuLanguage(page, "메뉴", "English");
  await expect(page.getByRole("dialog", { name: "Menu" })).toBeVisible();
  await expect.poll(tripReads).toBeGreaterThan(before);
  await pickMenuLanguage(page, "Menu", "한국어");
  await menuLink(page, "메뉴", "여행 목록 보기").click();
  await expect(page).toHaveURL(/\/trips$/);

  await expect(rows(page)).toHaveCount(1);
  await rows(page).first().getByRole("button").click();
  await confirmDialog(page).getByRole("button", { name: "삭제", exact: true }).click();
  await expect(said(page)).toHaveText("여행 1개를 삭제했어요.");
  await expect(page.locator("#main-content").getByText("아직 등록한 여행이 없어요.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "선택 삭제" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "새 여행 등록" })).toBeFocused();
  expect(await asked(server)).toEqual([TRIP_ID]);

  // 앱 안에서 지운 여행의 화면으로 돌아가도: 캐시된 옛 화면이 아니라 서버의 「없음」(404)을 읽어 오류 화면이 뜬다.
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));
  await expect(page.getByRole("heading", { name: "여행 정보를 불러오지 못했어요" })).toBeVisible();
  await expect(tripScreen(page)).toHaveCount(0);

  // 첫 화면 카드도 삭제를 따른다.
  await page.getByRole("banner").getByRole("link", { name: "triPilot — 소개 화면으로 돌아가기" }).click();
  await expect(card(page).getByText("아직 등록한 여행이 없어요.", { exact: true })).toBeVisible();

  // 새로고침해도 돌아오지 않는다(서버가 지웠다).
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(page.getByRole("heading", { name: "여행 정보를 불러오지 못했어요" })).toBeVisible();
  await page.goto("/trips");
  await expect(page.locator("#main-content").getByText("아직 등록한 여행이 없어요.", { exact: true })).toBeVisible();
});

test("영어·키보드로 한 건 삭제와 선택 삭제를 쓰고, PC 기기 틀·375px·320px에서 제목·버튼·행이 겹치거나 넘치지 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ trips: 3 });
  await page.goto("/trips");
  await expect(rows(page)).toHaveCount(3);
  const ids = await shownIds(page);
  await openMenu(page, "메뉴");
  await pickMenuLanguage(page, "메뉴", "English");
  await page.keyboard.press("Escape");
  const trash = rows(page).first().getByRole("button");
  // 제목은 서버가 준 그대로(영어로 옮기지 않는다) — 이름의 틀만 영어다.
  await expect(trash).toHaveAccessibleName(/^Delete 내 여행 \(added .+\)$/);

  // Enter 가 확인창을 열고, Escape 가 휴지통으로 돌려보내고, Tab 이 Delete 에 닿고, Enter 가 지운다.
  await trash.focus();
  await page.keyboard.press("Enter");
  const dialog = confirmDialog(page);
  await expect(dialog).toHaveAccessibleName("Delete this trip?");
  await expect(dialog).toContainText("The trip, its chat and its plan link saved on the server will be deleted, and its alerts stop. This can’t be undone.");
  await page.keyboard.press("Escape");
  await expect(trash).toBeFocused();
  expect(await asked(server)).toEqual([]);
  await page.keyboard.press("Enter");
  await page.keyboard.press("Tab");
  await expect(dialog.getByRole("button", { name: "Delete", exact: true })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(said(page)).toHaveText("Deleted 1 trip.");
  await expect(rows(page)).toHaveCount(2);
  expect(await asked(server)).toEqual([ids[0]]);

  // 선택 모드: Tab 은 꺼진 Delete (0) 을 건너 첫 체크박스로 가고, Space 가 고른다.
  const select = page.getByRole("button", { name: "Select to delete" });
  await expect(select).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: "Cancel", exact: true })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("checkbox").first()).toBeFocused();
  await page.keyboard.press("Space");
  await expect(page.getByRole("button", { name: "Delete (1)" })).toBeEnabled();

  /** 제목 줄의 단추가 제목과 겹치지 않고, 모든 행의 부분이 행 안에서 나란히 놓인다. */
  const fits = () => page.locator("#main-content").evaluate((main) => {
    const box = (element: Element) => element.getBoundingClientRect();
    const title = box(main.querySelector("header h1")!);
    const clear = [...main.querySelectorAll("header button")].every((button) => box(button).left >= title.right - .5 || box(button).top >= title.bottom - .5);
    const inRows = [...main.querySelectorAll("li")].every((row) => {
      // 행의 부분을 왼쪽부터: 선택 모드는 체크박스와 글, 아니면 글·화살표·휴지통.
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

// ── 새로 더한 시험: 서버 쪽 삭제의 두 가지 어긋남 ───────────────────────────────────────────

test("서버가 여행 삭제를 아직 모르면(404) 안내 알림이 뜨고, 선택 삭제·휴지통이 꺼지며, 목록은 그대로이고 서버에는 삭제 요청이 한 번만 간다", async ({ page, request }) => {
  const server = mockServer(request);
  // 「경로가 없다」 = 실서버가 지금 주는 답과 같다: 404 `{"detail":"Not Found"}` (여행이 없다는 서버 문장이 아니다).
  await server.scenario({ trips: 3, tripDelete: "unsupported" });
  const answers = watchDeletes(page);
  await page.goto("/trips");
  await expect(rows(page)).toHaveCount(3);
  const ids = await shownIds(page);
  await expect(page.getByRole("button", { name: "선택 삭제" })).toBeEnabled();   // 눌러 보기 전에는 모른다

  await rows(page).first().getByRole("button").click();
  await confirmDialog(page).getByRole("button", { name: "삭제", exact: true }).click();
  await expect(warned(page)).toHaveText("서버가 아직 여행 삭제를 지원하지 않아요. 지원되면 바로 쓸 수 있어요.");
  await expect(said(page)).toHaveText("");
  await expect(confirmDialog(page)).toHaveCount(0);
  // 이제 알았으니 삭제 길이 모두 꺼진다.
  await expect(page.getByRole("button", { name: "선택 삭제" })).toBeDisabled();
  await expect(rows(page).getByRole("button")).toHaveCount(3);
  for (const bin of await rows(page).getByRole("button").all()) await expect(bin).toBeDisabled();
  // 꺼진 「선택 삭제」 대신 초점은 「새 여행 등록」으로 간다.
  await expect(page.getByRole("link", { name: "새 여행 등록", exact: true })).toBeFocused();
  // 목록은 그대로이고, 서버에 간 것은 방금 그 요청 하나(404)뿐이다.
  expect(await shownIds(page)).toEqual(ids);
  expect(await asked(server)).toEqual([ids[0]]);
  await expect.poll(() => [...answers]).toEqual([404]);
});

test("삭제가 서버 오류(500)로 실패하면 실패 알림만 뜨고 목록·삭제 단추는 그대로이며, 서버가 나으면 다시 눌러 지울 수 있다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ trips: 3, tripDelete: "fail" });
  const answers = watchDeletes(page);
  await page.goto("/trips");
  await expect(rows(page)).toHaveCount(3);
  const ids = await shownIds(page);

  const trash = rows(page).first().getByRole("button");
  await trash.click();
  await confirmDialog(page).getByRole("button", { name: "삭제", exact: true }).click();
  await expect(warned(page)).toHaveText("삭제하지 못했어요. 다시 시도해 주세요.");
  await expect(said(page)).toHaveText("");
  await expect(confirmDialog(page)).toHaveCount(0);
  await expect(rows(page)).toHaveCount(3);
  expect(await shownIds(page)).toEqual(ids);
  await expect(trash).toBeFocused();
  // 「지원 안 함」이 아니라 일시 실패다: 삭제 길은 꺼지지 않는다.
  await expect(trash).toBeEnabled();
  await expect(page.getByRole("button", { name: "선택 삭제" })).toBeEnabled();
  expect(await asked(server)).toEqual([ids[0]]);
  await expect.poll(() => [...answers]).toEqual([500]);

  // 서버가 나으면 같은 화면에서 다시 눌러 지운다. 앞의 실패 알림은 새로 물을 때 사라진다.
  await server.scenario({ tripDelete: "ok" });
  await trash.click();
  await expect(warned(page)).toHaveText("");
  await confirmDialog(page).getByRole("button", { name: "삭제", exact: true }).click();
  await expect(said(page)).toHaveText("여행 1개를 삭제했어요.");
  await expect(warned(page)).toHaveText("");
  await expect(rows(page)).toHaveCount(2);
  expect(await shownIds(page)).toEqual([ids[1], ids[2]]);
  expect(await asked(server)).toEqual([ids[0], ids[0]]);
  await expect.poll(() => [...answers]).toEqual([500, 200]);
  await page.reload();
  await expect(rows(page)).toHaveCount(2);
  expect(await shownIds(page)).toEqual([ids[1], ids[2]]);
});
