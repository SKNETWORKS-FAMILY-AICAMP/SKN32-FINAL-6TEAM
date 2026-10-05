import { expect, test, type Locator, type Page } from "@playwright/test";
import { agreeTerms, forgetStartScreen, mockServer, noHorizontalScroll, openPreferencesFromMyPage, pickMenuLanguage, registerStubTrip, TRIP_ID, useKorean } from "./helpers";

test.beforeEach(async ({ page, request }) => { await mockServer(request).reset(); await useKorean(page); });

/** The six question titles, in order (no separate transport or nationality question). */
const TITLES = ["어떤 여행을 좋아하세요?", "누구와 함께 떠나나요?", "어떤 것을 더 중요하게 생각하나요?", "실내와 실외 중 어디가 좋으세요?", "갑자기 일정이 꼬이면 어떻게 했으면 좋겠어요?", "여행할 때 어느 정도 여유가 좋으세요?"];
const PARTY = 1, PRIORITY = 2, INDOOR = 3;
const heading = (page: Page, name: string) => page.getByRole("heading", { name, exact: true });
const skip = (page: Page) => page.getByRole("button", { name: "응답하지 않고 넘어가기" });
const next = (page: Page) => page.getByRole("button", { name: "다음", exact: true });
const back = (page: Page) => page.getByRole("button", { name: "이전", exact: true });
const area = (page: Page, name: "음식" | "활동" | "이동") => page.getByRole("button", { name: new RegExp(`^${name}`) });
const detail = (page: Page, name: string) => page.locator("[id^=details-]").getByRole("button", { name: new RegExp(`^${name}`) });
/** The rank number a control shows. Assertions on it retry until the screen has updated. */
const rank = (control: Locator) => control.locator("span[aria-hidden=true]").last();
/** The finished-survey summary lives in the preferences card's content. */
const summary = (page: Page) => page.locator("#content-2");
/** The two finished-survey cards, one of them by its title, and the position line under them. */
const summaryCards = (page: Page, name = "나의 여행 취향") => page.getByRole("region", { name });
const summaryCard = (page: Page, title: string) => page.locator(`[role=group][aria-label$="· ${title}"]`);
const place = (page: Page) => summaryCards(page).locator("p[aria-live]");
/** Each row of a summary card as [question name, ...answer lines]. */
const rows = (card: Locator) => card.locator("strong").evaluateAll((values) => values.map((value) => [value.previousElementSibling!.textContent, ...[...value.children].map((line) => line.textContent)]));

/**
 * Wait until question `index` has finished sliding in: its title takes focus at the end of the slide. The carousel
 * ignores next/back/skip presses during a slide on purpose (no double moves), so every move waits for this.
 */
const settled = (page: Page, index: number) => expect(page.locator(`#question-title-${index}`)).toBeFocused();

async function openSurvey(page: Page) {
  // [2026-10-06] 처음 동의하면 계획 화면을 거쳐 취향으로 돌아오므로, 그 사이 서버 쪽 세션이 생긴다 - 그 세션에 여행은 아직 없다(「여행 계획 등록하기」가 보이는 처음 모양).
  await mockServer(page.request).scenario({ trips: "none" });
  await page.goto("/start");
  // ★`[2026-10-01]` The start screen keeps its answers in this browser; every run here starts from the first-time screen.
  await forgetStartScreen(page);
  await page.getByRole("button", { name: /약관 동의/ }).click();
  await agreeTerms(page);
  await page.getByRole("button", { name: "시작하기" }).click();
  await settled(page, 0);
  await expect(heading(page, TITLES[0])).toBeVisible();
}

/** From question 0, skip one by one up to question `index`. */
async function skipTo(page: Page, index: number) {
  for (let at = 0; at < index; at += 1) {
    await skip(page).click();
    await settled(page, at + 1);
  }
  await expect(heading(page, TITLES[index])).toBeVisible();
}

/** From question `from` (already sliding in), skip the rest to reach the summary. */
async function skipRest(page: Page, from: number) {
  for (let at = from; at < TITLES.length; at += 1) {
    await settled(page, at);
    await skip(page).click();
  }
  await expect(heading(page, "여행 취향 설정 완료")).toBeVisible();
}

test("여행자 구성의 기타는 입력란을 열고, 공백만으로는 못 넘어가며, 입력한 내용이 요약에 보이고, 다른 선택지로 바꾸면 숨겨졌다가 다시 고르면 초안이 돌아온다", async ({ page }) => {
  await openSurvey(page);
  await skipTo(page, PARTY);
  const field = page.getByRole("textbox", { name: "누구와 함께 여행하는지 알려 주세요." });
  await expect(field).toHaveCount(0);
  await page.getByRole("button", { name: "기타", exact: true }).click();
  await expect(field).toBeVisible();
  await expect(next(page)).toBeDisabled();
  await field.fill("   ");
  await expect(next(page)).toBeDisabled();
  await field.fill("  직장 동료  ");
  await expect(next(page)).toBeEnabled();

  await page.getByRole("button", { name: "친구", exact: true }).click();
  await expect(field).toHaveCount(0);
  await expect(next(page)).toBeEnabled();
  await page.getByRole("button", { name: "기타", exact: true }).click();
  await expect(field).toHaveValue("  직장 동료  ");

  await next(page).click();
  await skipRest(page, PRIORITY);
  await expect(summary(page)).toContainText("직장 동료");
  await expect(summary(page)).not.toContainText("기타");
});

test("여행자 구성을 건너뛰면 선택과 기타 입력이 함께 지워지고, 다른 선택지를 고르면 요약에는 그 선택지만 보인다", async ({ page }) => {
  await openSurvey(page);
  await skipTo(page, PARTY);
  await page.getByRole("button", { name: "기타", exact: true }).click();
  await page.getByRole("textbox", { name: "누구와 함께 여행하는지 알려 주세요." }).fill("직장 동료");
  await skip(page).click();
  await settled(page, PRIORITY);
  await back(page).click();
  await settled(page, PARTY);
  await expect(page.getByRole("button", { name: "기타", exact: true })).toHaveAttribute("aria-pressed", "false");
  await page.getByRole("button", { name: "기타", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "누구와 함께 여행하는지 알려 주세요." })).toHaveValue("");
  await page.getByRole("textbox", { name: "누구와 함께 여행하는지 알려 주세요." }).fill("직장 동료");
  await page.getByRole("button", { name: "친구", exact: true }).click();
  await next(page).click();
  await skipRest(page, PRIORITY);
  await expect(summary(page)).toContainText("친구");
  await expect(summary(page)).not.toContainText("직장 동료");
});

test("설문은 6문항이고 이동수단·내국인 여부 질문이 없으며, 진행률과 번호가 6에 맞는다", async ({ page }) => {
  await openSurvey(page);
  await expect(page.getByText("6가지 질문으로 여행 취향을 알아봐요.")).toHaveCount(1);
  const progress = page.getByRole("progressbar", { name: "답변한 질문" });
  await expect(progress).toHaveAttribute("aria-valuemax", "6");
  for (const [at, title] of TITLES.entries()) {
    await settled(page, at);
    await expect(heading(page, title)).toBeVisible();
    for (const gone of ["어떻게 이동하고 싶나요?", "한국 국적이신가요?"]) await expect(heading(page, gone)).toHaveCount(0);
    await skip(page).click();
    if (at < TITLES.length - 1) await expect(progress).toHaveAttribute("aria-valuenow", String(at + 1));
  }
  await expect(heading(page, "여행 취향 설정 완료")).toBeVisible();
});

test("분야는 누른 순서로 1·2·3이 붙고, 해제하면 뒤 번호가 당겨지고 세부 답이 지워지며, 다시 고르면 마지막에 붙는다 — 카드 위치는 그대로다", async ({ page }) => {
  await openSurvey(page);
  await skipTo(page, PRIORITY);
  const tops = async () => Promise.all((["음식", "활동", "이동"] as const).map(async (name) => (await area(page, name).boundingBox())!.y));
  const before = await tops();
  expect([...before].sort((a, b) => a - b)).toEqual(before);

  await area(page, "음식").click();
  await area(page, "이동").click();
  await area(page, "활동").click();
  await expect(rank(area(page, "음식"))).toHaveText("1");
  await expect(rank(area(page, "이동"))).toHaveText("2");
  await expect(rank(area(page, "활동"))).toHaveText("3");
  const after = await tops();
  expect([...after].sort((a, b) => a - b)).toEqual(after);

  await detail(page, "택시").click();
  await detail(page, "힐링").click();
  await expect(area(page, "이동")).toHaveAttribute("aria-pressed", "true");
  await area(page, "이동").click();
  await expect(area(page, "이동")).toHaveAttribute("aria-pressed", "false");
  await expect(rank(area(page, "음식"))).toHaveText("1");
  await expect(rank(area(page, "활동"))).toHaveText("2");
  await expect(page.locator("#details-mobility")).toBeHidden();
  await expect(detail(page, "힐링")).toHaveAttribute("aria-pressed", "true");     // other areas keep their details

  await area(page, "이동").click();
  await expect(rank(area(page, "이동"))).toHaveText("3");
  await expect(detail(page, "택시")).toHaveAttribute("aria-pressed", "false");     // cleared when the area was dropped
});

test("세부 항목도 누른 순서로 번호가 붙고, 해제·재선택 규칙이 같으며, 누른다고 분야 선택이 바뀌지 않는다 — 이동은 네 항목", async ({ page }) => {
  await openSurvey(page);
  await skipTo(page, PRIORITY);
  await area(page, "음식").click();
  for (const name of ["맛", "친절", "청결"]) await detail(page, name).click();
  await expect(rank(detail(page, "맛"))).toHaveText("1");
  await expect(rank(detail(page, "친절"))).toHaveText("2");
  await expect(rank(detail(page, "청결"))).toHaveText("3");
  await detail(page, "맛").click();
  await expect(rank(detail(page, "친절"))).toHaveText("1");
  await expect(rank(detail(page, "청결"))).toHaveText("2");
  await detail(page, "맛").click();
  await expect(rank(detail(page, "맛"))).toHaveText("3");
  await expect(area(page, "음식")).toHaveAttribute("aria-pressed", "true");
  await expect(rank(area(page, "음식"))).toHaveText("1");

  await area(page, "이동").click();
  await expect(page.locator("#details-mobility").getByRole("button")).toHaveText([/^대중교통/, /^도보/, /^렌트카/, /^택시/]);
});

test("고른 분야마다 세부 항목이 하나 이상이면 다음이 켜지고, 고르지 않은 분야는 묻지 않으며, 건너뛰면 모두 초기화된다", async ({ page }) => {
  await openSurvey(page);
  await skipTo(page, PRIORITY);
  await expect(next(page)).toBeDisabled();
  await area(page, "활동").click();
  await expect(next(page)).toBeDisabled();
  await detail(page, "DIY").click();
  await expect(next(page)).toBeEnabled();
  await area(page, "음식").click();
  await expect(next(page)).toBeDisabled();
  await detail(page, "청결").click();
  await expect(next(page)).toBeEnabled();

  await skip(page).click();
  await settled(page, INDOOR);
  await back(page).click();
  await settled(page, PRIORITY);
  for (const name of ["음식", "활동", "이동"] as const) await expect(area(page, name)).toHaveAttribute("aria-pressed", "false");
  await area(page, "활동").click();
  await expect(detail(page, "DIY")).toHaveAttribute("aria-pressed", "false");
});

test("요약은 분야와 세부 항목을 실제로 고른 순서대로 보이고, 이전·다음이나 카드 접기로 답이 사라지지 않는다", async ({ page }) => {
  await openSurvey(page);
  await skipTo(page, PRIORITY);
  await area(page, "음식").click();
  await area(page, "이동").click();
  for (const name of ["청결", "맛", "택시", "대중교통"]) await detail(page, name).click();
  await next(page).click();
  await settled(page, INDOOR);
  await back(page).click();
  await settled(page, PRIORITY);
  await expect(rank(detail(page, "택시"))).toHaveText("1");
  // Fold the preferences card and open it again: the answers stay.
  await page.getByRole("button", { name: /여행 취향 알아보기/ }).first().click();
  await page.getByRole("button", { name: /여행 취향 알아보기/ }).click();
  await expect(heading(page, TITLES[PRIORITY])).toBeVisible();
  await expect(rank(detail(page, "청결"))).toHaveText("1");
  await next(page).click();
  await skipRest(page, INDOOR);
  // Both lines, in picking order, one after the other.
  await expect(summary(page)).toContainText("1. 음식 — 청결 → 맛2. 이동 — 택시 → 대중교통");
});

test("영어·키보드로 통합 카드를 쓰고, PC 기기 틀·375px·320px에서 세부 항목이 줄바꿈되어 번호가 글자를 덮거나 넘치지 않으며 다음 버튼에 닿는다", async ({ page }) => {
  for (const [width, height] of [[1280, 900], [375, 812], [320, 640]]) {
    await page.setViewportSize({ width, height });
    await openSurvey(page);
    await skipTo(page, PRIORITY);
    for (const name of ["음식", "이동", "활동"] as const) await area(page, name).click();
    for (const name of ["청결", "맛", "친절", "택시", "대중교통", "도보", "렌트카", "익스트림", "힐링", "DIY", "쇼핑"]) await detail(page, name).click();
    await noHorizontalScroll(page);
    const clear = await page.locator("[id^=details-] button").evaluateAll((buttons) => buttons.every((button) => {
      const badge = button.querySelector("span[aria-hidden=true]")!.getBoundingClientRect();
      const words = document.createRange();
      words.selectNodeContents(button.firstChild!);
      const text = words.getBoundingClientRect(), box = button.getBoundingClientRect(), card = button.closest("[id^=details-]")!.parentElement!.getBoundingClientRect();
      return text.right <= badge.left + .5 && box.right <= card.right + .5 && box.left >= card.left - .5;
    }));
    expect(clear, `${width}x${height}`).toBe(true);
    await next(page).scrollIntoViewIfNeeded();
    await expect(next(page)).toBeInViewport();
    await expect(next(page)).toBeEnabled();
  }

  // Keyboard: Space picks an area, Tab reaches its details, Enter picks one.
  await openSurvey(page);
  await skipTo(page, PRIORITY);
  await area(page, "이동").focus();
  await page.keyboard.press("Space");
  await expect(rank(area(page, "이동"))).toHaveText("1");
  await page.keyboard.press("Tab");
  await expect(detail(page, "대중교통")).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(rank(detail(page, "대중교통"))).toHaveText("1");
  await expect(next(page)).toBeEnabled();

  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await pickMenuLanguage(page, "메뉴", "English");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("heading", { name: "What matters more to you?", exact: true })).toBeVisible();
  await expect(page.getByText("Pick areas and details in order of importance.")).toBeVisible();
  await expect(page.getByRole("button", { name: /^Getting around/ })).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#details-mobility").getByRole("button")).toHaveText([/^Public transit/, /^Walking/, /^Rental car/, /^Taxi/]);
});

test("완료 화면은 기본사항·여행 방식 두 장에 선택 언어와 6문항의 답을 고른 순서대로 빠짐없이 보이고, 건너뛴 질문은 응답하지 않음이다", async ({ page }) => {
  await openSurvey(page);
  await page.getByRole("button", { name: "문화와 역사", exact: true }).click();
  await next(page).click();
  await settled(page, PARTY);
  await page.getByRole("button", { name: "기타", exact: true }).click();
  await page.getByRole("textbox", { name: "누구와 함께 여행하는지 알려 주세요." }).fill("  대학 동기 여섯 명과 그 가족들  ");
  await next(page).click();
  await settled(page, PRIORITY);
  await area(page, "활동").click();
  await area(page, "음식").click();
  for (const name of ["쇼핑", "힐링", "청결", "맛"]) await detail(page, name).click();
  await next(page).click();
  await settled(page, INDOOR);
  await page.getByRole("button", { name: "실내", exact: true }).first().click();
  await page.getByRole("button", { name: "상관없음", exact: true }).last().click();
  await next(page).click();
  await settled(page, 4);
  await skip(page).click();
  await settled(page, 5);
  await page.getByRole("button", { name: "꽉 차게", exact: true }).click();
  await page.getByRole("button", { name: "설정 완료" }).click();

  await expect(heading(page, "여행 취향 설정 완료")).toBeVisible();
  await expect(page.getByText("옆으로 넘겨 선택한 답변을 확인해 주세요.")).toBeVisible();
  expect(await rows(summaryCard(page, "기본사항"))).toEqual([["선택 언어", "한국어"], ["여행 테마", "문화와 역사"], ["여행자 구성", "대학 동기 여섯 명과 그 가족들"]]);
  expect(await rows(summaryCard(page, "여행 방식"))).toEqual([
    ["여행 우선순위", "1. 활동 — 쇼핑 → 힐링", "2. 음식 — 청결 → 맛"],
    ["실내·실외", "식당 · 실내", "액티비티 · 상관없음"],
    ["일정 변경 방식", "응답하지 않음"],
    ["여행 여유", "꽉 차게"],
  ]);
  await expect(summary(page)).not.toContainText("내국인");
});

test("요약 카드는 버튼·마우스 끌기·가로 스크롤·키보드로 두 장만 오가고, 위치 표시가 보이는 카드와 맞으며, 아래 버튼 위치와 답은 그대로다", async ({ page }) => {
  await openSurvey(page);
  await page.getByRole("button", { name: "맛집 탐방", exact: true }).click();
  await next(page).click();
  await skipRest(page, PARTY);
  const cards = summaryCards(page), previous = cards.getByRole("button", { name: "이전 카드" }), forward = cards.getByRole("button", { name: "다음 카드" });
  const primary = page.getByRole("button", { name: "여행 계획 등록하기" });
  const answers = await rows(summaryCard(page, "기본사항"));
  /** Where the main button sits below the carousel top: page scrolling moves both, a card change must not. */
  const offset = async () => (await primary.boundingBox())!.y - (await cards.boundingBox())!.y;
  const before = await offset();

  /** The card shown fits inside the carousel (the other one only peeks in), and the position line, hidden state and ends match it. */
  async function showing(index: 0 | 1) {
    const [name, other] = index === 0 ? ["기본사항", "여행 방식"] : ["여행 방식", "기본사항"];
    await expect(place(page)).toHaveText(`${index + 1} / 2 · ${name}`);
    await expect(summaryCard(page, name)).toHaveAttribute("aria-hidden", "false");
    await expect(summaryCard(page, other)).toHaveAttribute("aria-hidden", "true");
    await expect(previous).toHaveAttribute("aria-disabled", String(index === 0));
    await expect(forward).toHaveAttribute("aria-disabled", String(index === 1));
    await expect.poll(async () => {
      const card = (await summaryCard(page, name).boundingBox())!, view = (await cards.boundingBox())!;
      return card.x >= view.x - 1 && card.x + card.width <= view.x + view.width + 1;
    }).toBe(true);
  }

  // The end buttons stay pressable (aria-disabled keeps their focus) but do nothing; `force` presses them anyway.
  await showing(0);
  await previous.click({ force: true });
  await showing(0);
  await forward.click();
  await showing(1);
  await forward.click({ force: true });
  await showing(1);
  // Both cards take the taller one's height, so the buttons below do not move.
  const heights = await Promise.all(["기본사항", "여행 방식"].map(async (name) => (await summaryCard(page, name).boundingBox())!.height));
  expect(heights[0]).toBe(heights[1]);
  expect(await offset()).toBe(before);
  await previous.click();
  await showing(0);

  // Mouse drag: 150px left goes on, 20px back stays, 150px right comes back. Grab the card's middle: its top can
  // sit under the sheet's sticky head, which folds the card when pressed.
  await summaryCard(page, "기본사항").scrollIntoViewIfNeeded();
  const box = (await summaryCard(page, "기본사항").boundingBox())!;
  async function dragBy(dx: number) {
    const x = box.x + box.width / 2, y = box.y + box.height / 2;
    await page.mouse.move(x, y);
    await page.mouse.down();
    await page.mouse.move(x + dx / 2, y);
    await page.mouse.move(x + dx, y);
    await page.mouse.up();
  }
  await dragBy(-150);
  await showing(1);
  await dragBy(20);
  await showing(1);
  await dragBy(150);
  await showing(0);

  // Touch and trackpads scroll the row natively: the position follows the scroll.
  await summaryCard(page, "기본사항").locator("..").evaluate((slides) => slides.scrollTo({ left: slides.scrollWidth }));
  await showing(1);

  // Keyboard: the buttons keep their focus at the ends, and no control inside a card takes focus.
  await previous.focus();
  await page.keyboard.press("Enter");
  await showing(0);
  await page.keyboard.press("Tab");
  await expect(forward).toBeFocused();
  await page.keyboard.press("Enter");
  await showing(1);
  await page.keyboard.press("Space");
  await expect(forward).toBeFocused();
  await showing(1);
  await expect(cards.locator("[role=group] :is(a, button, input, [tabindex])")).toHaveCount(0);

  expect(await rows(summaryCard(page, "기본사항"))).toEqual(answers);
  expect(await offset()).toBe(before);
});

test("여행 취향 수정하기는 답을 지킨 채 설문으로 돌아가고, 바꿔서 다시 마치면 요약 카드가 바뀐 답을 보인다", async ({ page }) => {
  await openSurvey(page);
  await page.getByRole("button", { name: "맛집 탐방", exact: true }).click();
  await next(page).click();
  await skipRest(page, PARTY);
  expect(await rows(summaryCard(page, "기본사항"))).toEqual([["선택 언어", "한국어"], ["여행 테마", "맛집 탐방"], ["여행자 구성", "응답하지 않음"]]);

  await page.getByRole("button", { name: "여행 취향 수정하기" }).click();
  await page.getByRole("button", { name: "시작하기" }).click();
  await settled(page, 0);
  await expect(page.getByRole("button", { name: "맛집 탐방", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "자연과 힐링", exact: true }).click();
  await next(page).click();
  await settled(page, PARTY);
  await page.getByRole("button", { name: "친구", exact: true }).click();
  await next(page).click();
  await skipRest(page, PRIORITY);
  await expect(place(page)).toHaveText("1 / 2 · 기본사항");
  expect(await rows(summaryCard(page, "기본사항"))).toEqual([["선택 언어", "한국어"], ["여행 테마", "자연과 힐링"], ["여행자 구성", "친구"]]);
});

test("영어와 PC 기기 틀·375px·320px에서 긴 답도 카드 안에서 줄바꿈되어 잘리지 않고, 두 카드 높이가 같고, 가로로 넘치지 않는다", async ({ page }) => {
  await openSurvey(page);
  await skipTo(page, PARTY);
  await page.getByRole("button", { name: "기타", exact: true }).click();
  await page.getByRole("textbox", { name: "누구와 함께 여행하는지 알려 주세요." }).fill("대학 동기 여섯 명과 그 가족들, 그리고 반려견 두 마리와 함께하는 아주 긴 여행");
  await next(page).click();
  await settled(page, PRIORITY);
  for (const name of ["음식", "이동", "활동"] as const) await area(page, name).click();
  for (const name of ["청결", "맛", "친절", "택시", "대중교통", "도보", "렌트카", "익스트림", "힐링", "DIY", "쇼핑"]) await detail(page, name).click();
  await next(page).click();
  await skipRest(page, INDOOR);

  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await pickMenuLanguage(page, "메뉴", "English");
  await page.keyboard.press("Escape");
  await expect(heading(page, "Travel preferences set")).toBeVisible();
  const cards = summaryCards(page, "Your travel preferences");
  await expect(cards.locator("p[aria-live]")).toHaveText("1 / 2 · The basics");
  expect(await rows(summaryCard(page, "The basics"))).toEqual([["Language", "English"], ["Travel theme", "Not answered"], ["Your companions", "대학 동기 여섯 명과 그 가족들, 그리고 반려견 두 마리와 함께하는 아주 긴 여행"]]);
  expect(await rows(summaryCard(page, "How you travel"))).toEqual([
    ["Your priorities", "1. Food — Cleanliness → Taste → Kindness", "2. Getting around — Taxi → Public transit → Walking → Rental car", "3. Activities — Extreme → Relaxation → DIY → Shopping"],
    ["Indoors or out", "Not answered"],
    ["When plans change", "Not answered"],
    ["Your pace", "Not answered"],
  ]);

  for (const [width, height] of [[1280, 900], [375, 812], [320, 640]]) {
    await page.setViewportSize({ width, height });
    await noHorizontalScroll(page);
    const fit = await cards.locator("[role=group]").evaluateAll((slides) => slides.map((slide) => {
      const box = slide.getBoundingClientRect();
      const inside = [...slide.querySelectorAll("strong")].every((value) => value.scrollWidth <= value.clientWidth && value.getBoundingClientRect().bottom <= box.bottom + .5);
      return { height: Math.round(box.height), inside };
    }));
    expect(fit.map((card) => card.inside), `${width}x${height}`).toEqual([true, true]);
    expect(fit[0].height, `${width}x${height}`).toBe(fit[1].height);
    const edit = page.getByRole("button", { name: "Edit your preferences" });
    await edit.scrollIntoViewIfNeeded();
    await expect(edit).toBeInViewport();
    const button = (await edit.boundingBox())!, card = (await page.locator("#card-2").boundingBox())!;
    expect(button.y + button.height, `${width}x${height}`).toBeLessThanOrEqual(card.y + card.height);
  }
});

test("여행을 등록해 관리를 시작한 뒤 다시 요약을 열면 주 버튼이 내 여행 이어보기로 바뀌고 그 여행으로 간다", async ({ page }) => {
  await openSurvey(page);
  await skipRest(page, 0);
  await expect(page.getByRole("button", { name: "내 여행 이어보기" })).toHaveCount(0);
  await page.getByRole("button", { name: "여행 계획 등록하기" }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await registerStubTrip(page);
  const tripId = TRIP_ID;

  // ★「내 여행 이어보기」 follows the server's trip list (the newest trip), not something this page remembers. The intro button
  // now goes straight to registering once the terms are agreed, so the preferences are reached from My page.
  await page.getByRole("banner").getByRole("link", { name: "triPilot 홈으로" }).click();
  await openPreferencesFromMyPage(page);
  const preferences = page.getByRole("button", { name: /여행 취향 알아보기/ }).first();
  if (await preferences.getAttribute("aria-expanded") !== "true") await preferences.click();
  await expect(heading(page, "여행 취향 설정 완료")).toBeVisible();
  await expect(page.getByRole("button", { name: "여행 계획 등록하기" })).toHaveCount(0);
  await page.getByRole("button", { name: "내 여행 이어보기" }).click();
  await expect(page).toHaveURL(new RegExp(`/trips/${tripId}$`));
});
