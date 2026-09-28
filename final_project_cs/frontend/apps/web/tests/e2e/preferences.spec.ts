import { expect, test, type Locator, type Page } from "@playwright/test";
import { agreeTerms, noHorizontalScroll, pickMenuLanguage, useKorean } from "./helpers/app";

test.beforeEach(async ({ page }) => { await useKorean(page); });

/** The seven question titles, in order (the transport question is gone). */
const TITLES = ["어떤 여행을 좋아하세요?", "누구와 함께 떠나나요?", "한국 국적이신가요?", "어떤 것을 더 중요하게 생각하나요?", "실내와 실외 중 어디가 좋으세요?", "갑자기 일정이 꼬이면 어떻게 했으면 좋겠어요?", "여행할 때 어느 정도 여유가 좋으세요?"];
const heading = (page: Page, name: string) => page.getByRole("heading", { name, exact: true });
const skip = (page: Page) => page.getByRole("button", { name: "응답하지 않고 넘어가기" });
const next = (page: Page) => page.getByRole("button", { name: "다음", exact: true });
const area = (page: Page, name: "음식" | "활동" | "이동") => page.getByRole("button", { name: new RegExp(`^${name}`) });
const detail = (page: Page, name: string) => page.locator("[id^=details-]").getByRole("button", { name: new RegExp(`^${name}`) });
/** The rank number a control shows. Assertions on it retry until the screen has updated. */
const rank = (control: Locator) => control.locator("span[aria-hidden=true]").last();
/** The finished-survey summary lives in the preferences card's content. */
const summary = (page: Page) => page.locator("#content-2");

async function openSurvey(page: Page) {
  await page.goto("/start");
  await page.getByRole("button", { name: /약관 동의/ }).click();
  await agreeTerms(page);
  await page.getByRole("button", { name: "시작하기" }).click();
  await expect(heading(page, TITLES[0])).toBeVisible();
}

/** Skip questions one by one, waiting for each next card, until `title` is shown. */
async function skipTo(page: Page, title: string) {
  for (const [at, item] of TITLES.entries()) {
    if (item === title) break;
    if (!(await heading(page, item).isVisible())) continue;
    await skip(page).click();
    await expect(heading(page, TITLES[at + 1])).toBeVisible();
  }
  await expect(heading(page, title)).toBeVisible();
}

test("여행자 구성의 기타는 입력란을 열고, 공백만으로는 못 넘어가며, 입력한 내용이 요약에 보이고, 다른 선택지로 바꾸면 숨겨졌다가 다시 고르면 초안이 돌아온다", async ({ page }) => {
  await openSurvey(page);
  await skipTo(page, TITLES[1]);
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
  for (const title of TITLES.slice(2)) {
    await expect(heading(page, title)).toBeVisible();
    await skip(page).click();
  }
  await expect(heading(page, "여행 취향을 모두 알아봤어요.")).toBeVisible();
  await expect(summary(page)).toContainText("직장 동료");
  await expect(summary(page)).not.toContainText("기타");
});

test("여행자 구성을 건너뛰면 선택과 기타 입력이 함께 지워지고, 다른 선택지를 고르면 요약에는 그 선택지만 보인다", async ({ page }) => {
  await openSurvey(page);
  await skipTo(page, TITLES[1]);
  await page.getByRole("button", { name: "기타", exact: true }).click();
  await page.getByRole("textbox", { name: "누구와 함께 여행하는지 알려 주세요." }).fill("직장 동료");
  await skip(page).click();
  await expect(heading(page, TITLES[2])).toBeVisible();
  await page.getByRole("button", { name: "이전", exact: true }).click();
  await expect(heading(page, TITLES[1])).toBeVisible();
  await expect(page.getByRole("button", { name: "기타", exact: true })).toHaveAttribute("aria-pressed", "false");
  await page.getByRole("button", { name: "기타", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "누구와 함께 여행하는지 알려 주세요." })).toHaveValue("");
  await page.getByRole("textbox", { name: "누구와 함께 여행하는지 알려 주세요." }).fill("직장 동료");
  await page.getByRole("button", { name: "친구", exact: true }).click();
  await next(page).click();
  for (const title of TITLES.slice(2)) {
    await expect(heading(page, title)).toBeVisible();
    await skip(page).click();
  }
  await expect(summary(page)).toContainText("친구");
  await expect(summary(page)).not.toContainText("직장 동료");
});

test("설문은 7문항이고 이동수단 질문이 없으며, 진행률과 번호가 7에 맞는다", async ({ page }) => {
  await openSurvey(page);
  await expect(page.getByText("7가지 질문으로 여행 취향을 알아봐요.")).toHaveCount(1);
  const progress = page.getByRole("progressbar", { name: "답변한 질문" });
  await expect(progress).toHaveAttribute("aria-valuemax", "7");
  for (const [at, title] of TITLES.entries()) {
    await expect(heading(page, title)).toBeVisible();
    await expect(heading(page, "어떻게 이동하고 싶나요?")).toHaveCount(0);
    await skip(page).click();
    if (at < TITLES.length - 1) await expect(progress).toHaveAttribute("aria-valuenow", String(at + 1));
  }
  await expect(heading(page, "여행 취향을 모두 알아봤어요.")).toBeVisible();
});

test("분야는 누른 순서로 1·2·3이 붙고, 해제하면 뒤 번호가 당겨지고 세부 답이 지워지며, 다시 고르면 마지막에 붙는다 — 카드 위치는 그대로다", async ({ page }) => {
  await openSurvey(page);
  await skipTo(page, TITLES[3]);
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
  await skipTo(page, TITLES[3]);
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
  await skipTo(page, TITLES[3]);
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
  await expect(heading(page, TITLES[4])).toBeVisible();
  await page.getByRole("button", { name: "이전", exact: true }).click();
  await expect(heading(page, TITLES[3])).toBeVisible();
  for (const name of ["음식", "활동", "이동"] as const) await expect(area(page, name)).toHaveAttribute("aria-pressed", "false");
  await area(page, "활동").click();
  await expect(detail(page, "DIY")).toHaveAttribute("aria-pressed", "false");
});

test("요약은 분야와 세부 항목을 실제로 고른 순서대로 보이고, 이전·다음이나 카드 접기로 답이 사라지지 않는다", async ({ page }) => {
  await openSurvey(page);
  await skipTo(page, TITLES[3]);
  await area(page, "음식").click();
  await area(page, "이동").click();
  for (const name of ["청결", "맛", "택시", "대중교통"]) await detail(page, name).click();
  await next(page).click();
  await expect(heading(page, TITLES[4])).toBeVisible();
  await page.getByRole("button", { name: "이전", exact: true }).click();
  await expect(rank(detail(page, "택시"))).toHaveText("1");
  // Fold the preferences card and open it again: the answers stay.
  await page.getByRole("button", { name: /여행 취향 알아보기/ }).first().click();
  await page.getByRole("button", { name: /여행 취향 알아보기/ }).click();
  await expect(heading(page, TITLES[3])).toBeVisible();
  await expect(rank(detail(page, "청결"))).toHaveText("1");
  await next(page).click();
  for (const title of TITLES.slice(4)) {
    await expect(heading(page, title)).toBeVisible();
    await skip(page).click();
  }
  // Both lines, in picking order, one after the other.
  await expect(summary(page)).toContainText("1. 음식 — 청결 → 맛2. 이동 — 택시 → 대중교통");
});

test("영어·키보드로 통합 카드를 쓰고, PC 기기 틀·375px·320px에서 세부 항목이 줄바꿈되어 번호가 글자를 덮거나 넘치지 않으며 다음 버튼에 닿는다", async ({ page }) => {
  for (const [width, height] of [[1280, 900], [375, 812], [320, 640]]) {
    await page.setViewportSize({ width, height });
    await openSurvey(page);
    await skipTo(page, TITLES[3]);
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
  await skipTo(page, TITLES[3]);
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
