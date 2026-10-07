import { expect, test, type Page } from "@playwright/test";
import { checkPlan, mockServer, start, TRIP_ID } from "./helpers";

/**
 * `[2026-10-06 사용자 지시 — 첫 화면 · 확인 화면과 일관되게 전체를 모바일 기준으로, 메뉴에서 데스크탑을 고르면 그때 데스크탑 화면]` 계획 담기 · 내 여행 · 여행 · 마이페이지는 기본으로 휴대폰 크기 틀 안에 있고, 메뉴의
 * 「데스크탑 화면으로 보기」를 켜면 넓은 화면이 된다. 항로 지킴이 카드와 알림은 그 틀 안에서 틀 폭에 맞게 뜨고, 한 번 켜면 켜진 상태가 기본이다. 테스트용 mock 서버로 도는 자동 시험이다(화면 반응 — 실서버 확인 아님).
 */
const PLAN = "10/1 09:00 경복궁 관람";
const device = (page: Page) => page.locator('[class*="__device"]').first();

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

test("기본은 휴대폰 크기 틀이다 — 넓은 창(1280)에서도 계획 담기 · 내 여행 · 여행 · 마이페이지가 틀 폭(402px 이하) 안에 있고 가로로 넘치지 않는다", async ({ page, request }) => {
  await mockServer(request).scenario({ trips: "one", guardian: "on" });
  await page.setViewportSize({ width: 1280, height: 900 });
  await start(page);
  for (const path of ["/trips/new", "/trips", `/trips/${TRIP_ID}`, "/mypage"]) {
    await page.goto(path);
    await expect(device(page)).toBeVisible();
    const frame = (await device(page).boundingBox())!;
    expect(frame.width).toBeLessThanOrEqual(402.5);
    const main = (await page.locator("#main-content").boundingBox())!;
    expect(main.width).toBeLessThanOrEqual(402.5);
    expect(main.x).toBeGreaterThanOrEqual(frame.x - 1);
    expect(await device(page).evaluate((element) => { const scroller = element.querySelector('[class*="__scroll"]') as HTMLElement | null; return scroller ? scroller.scrollWidth <= scroller.clientWidth : true; })).toBe(true);
  }
});

test("메뉴의 「데스크탑 화면으로 보기」를 켜면 넓은 화면이 되고(이 브라우저가 기억한다), 끄면 다시 휴대폰 크기 틀이다", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await start(page);
  await page.goto("/trips/new");
  const narrow = (await page.locator("#main-content").boundingBox())!.width;
  expect(narrow).toBeLessThanOrEqual(402.5);
  await page.getByRole("button", { name: "메뉴" }).click();
  const toggle = page.getByRole("switch", { name: "데스크탑 화면으로 보기" });
  await expect(toggle).not.toBeChecked();
  await toggle.click();                                                                                  // 켜는 순간 화면 틀이 바뀌어 메뉴도 새로 그려진다
  await expect.poll(async () => (await page.locator("#main-content").boundingBox())!.width).toBeGreaterThan(600);
  await page.reload();                                                                                  // 기억한다
  await expect.poll(async () => (await page.locator("#main-content").boundingBox())!.width).toBeGreaterThan(600);
  await page.getByRole("button", { name: "메뉴" }).click();
  await page.getByRole("switch", { name: "데스크탑 화면으로 보기" }).click();
  await expect.poll(async () => (await page.locator("#main-content").boundingBox())!.width).toBeLessThanOrEqual(402.5);
});

test("항로 지킴이 카드는 휴대폰 틀 안에서 틀 폭에 맞는 아래 시트로 뜬다(화면 전체를 덮는 따로 노는 카드가 아니다)", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  const card = page.getByRole("dialog");
  await expect(card).toBeVisible();
  await page.waitForTimeout(450);
  const [frame, sheet] = [(await device(page).boundingBox())!, (await card.boundingBox())!];
  expect(sheet.x).toBeGreaterThanOrEqual(frame.x - 1);
  expect(sheet.x + sheet.width).toBeLessThanOrEqual(frame.x + frame.width + 1);
  expect(sheet.width).toBeGreaterThan(frame.width - 8);                                                  // 틀 폭에 맞는다
  expect(sheet.y + sheet.height).toBeLessThanOrEqual(frame.y + frame.height + 1);
});

test("항로 지킴이를 끄면 알림이 틀 안에서 틀 폭에 맞는 하얀 카드로 뜨고 몇 초 뒤 저절로 사라진다. 메뉴 서랍 머리의 아이콘은 메뉴 버튼과 같은 흰색 반투명이고 위에 말풍선이 없다", async ({ page, request }) => {
  await mockServer(request).scenario({ guardian: "on" });
  await page.setViewportSize({ width: 1280, height: 900 });
  await start(page);
  await page.goto(`/trips/${TRIP_ID}`);
  await page.getByRole("button", { name: "메뉴", exact: true }).click();                                // `[2026-10-07 목업 C안]` 여행의 아이콘은 메뉴 서랍 머리(닫기 ✕ 왼쪽)에 있다
  const icon = page.getByRole("button", { name: "항로 지킴이 끄기" });
  await expect(icon).toBeVisible();
  // 메뉴 버튼과 같은 바탕(반투명 흰색)
  const look = await page.evaluate(() => {
    const css = (selector: string) => { const style = getComputedStyle(document.querySelector(selector)!); return { background: style.backgroundColor, border: style.borderTopWidth, radius: style.borderTopLeftRadius }; };
    return { icon: css('button[aria-label="항로 지킴이 끄기"]'), menu: css('button[aria-label="메뉴"]') };
  });
  expect(look.icon.background).toBe(look.menu.background);
  expect(look.icon.border).toBe(look.menu.border);
  // 아이콘 위에 말풍선(::before 도구 설명)이 없다
  await icon.hover();
  expect(await icon.evaluate((element) => getComputedStyle(element, "::before").content)).toBe("none");
  await icon.click();
  const toast = page.getByRole("status").filter({ hasText: "항로 지킴이를 껐어요. 문제가 생기면 물어볼게요." });
  await expect(toast).toBeVisible();
  const [frame, bar] = [(await device(page).boundingBox())!, (await toast.boundingBox())!];
  expect(bar.x).toBeGreaterThanOrEqual(frame.x - 1);
  expect(bar.x + bar.width).toBeLessThanOrEqual(frame.x + frame.width + 1);
  expect(await toast.evaluate((element) => getComputedStyle(element).backgroundColor)).not.toBe(look.menu.background);   // 알림의 하얀 카드(메뉴 버튼의 반투명 바탕과는 다른 값)
  await expect(toast).toHaveCount(0, { timeout: 9000 });                                                  // 저절로 사라진다
});

test("한 번 켜면 켜진 상태가 기본이다 — 다음 계획에서는 카드를 다시 묻지 않고, 머리줄 아이콘은 처음부터 켜져 있다. 끄면 다시 묻는다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 0, trips: "none" });
  await page.setViewportSize({ width: 1280, height: 900 });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await checkPlan(page, "켜고 진행");                                                                    // 처음에는 묻는다
  await expect(page).toHaveURL(/\/(intakes|trips)\//, { timeout: 15_000 });
  // 같은 브라우저에서 새 계획: 아이콘이 처음부터 켜져 있고, 누르면 카드 없이 바로 진행한다
  await page.goto("/trips/new");
  await expect(page.getByRole("button", { name: "항로 지킴이 끄기" })).toBeVisible();
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page).toHaveURL(/\/(intakes|trips)\//, { timeout: 15_000 });
  const plans = await server.received("POST", "/plan");
  const intakes = await server.received("POST", "/v1/web/trip-intakes");
  expect(intakes.length).toBeGreaterThanOrEqual(2);
  void plans;
  // 끄면 기억을 지운다 — 새 창(이 탭의 결정이 아닌 새 시작)에서는 다시 묻는다
  await page.goto("/trips/new");
  await page.getByRole("button", { name: "항로 지킴이 끄기" }).click();
  const fresh = await page.context().newPage();
  await fresh.setViewportSize({ width: 1280, height: 900 });
  await fresh.goto("/trips/new");
  await expect(fresh.getByRole("button", { name: /^항로 지킴이 (끄기|켜기)$/ })).toHaveCount(0);       // 정한 적 없는 상태로 시작한다
  await fresh.getByLabel("나의 여행 계획").fill(PLAN);
  await fresh.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(fresh.getByRole("dialog")).toBeVisible();
});

test("계획이 비어 있으면 「계획 확인하기」는 꺼진 모양(회색 · aria-disabled)이지만 눌러 보면 입력칸 바로 아래에 무엇을 해야 하는지 알린다", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await start(page);
  await page.goto("/trips/new");
  const button = page.getByRole("button", { name: "계획 확인하기" });
  await expect(button).toHaveAttribute("aria-disabled", "true");
  await expect(button).not.toHaveAttribute("disabled");                                                  // 누를 수는 있다(눌러야 이유를 말한다)
  await button.click({ force: true });
  const notice = page.locator("#plan-error");
  await expect(notice).toContainText("여행 계획을 적거나 파일을 올려 주세요.");
  await expect(notice).toBeInViewport();
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await expect(button).not.toHaveAttribute("aria-disabled", "true");                                     // 쓰면 켜진 모양이 된다
});
