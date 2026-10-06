import { expect, test, type Page } from "@playwright/test";
import { checkPlan, fillPlanAsk, mockServer, openRegistration, start, weekAhead } from "./helpers";

/**
 * `[2026-10-06 사용자 지시 — 설문 화면 구현 인계 1단계]` 「읽는 기준」(하루 일정의 여유) · 항로 지킴이 카드 · 머리줄 아이콘과 되돌리기 줄.
 * 테스트용 mock 서버로 도는 자동 시험이다(화면 반응을 본다 — 실서버 확인 아님).
 */
const PLAN = "10/1 09:00 경복궁 관람";
const send = (page: Page) => page.getByRole("button", { name: "계획 확인하기" });
const card = (page: Page) => page.getByRole("dialog");

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

test("「계획 확인하기」를 누르면 읽기 전에 항로 지킴이 카드가 열리고, 초점은 단추가 아니라 제목에 있고, 서버로는 아직 아무것도 가지 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page);
  await openRegistration(page);
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await send(page).click();
  await expect(card(page)).toBeVisible();
  await expect(card(page).getByRole("heading", { name: /항로 지킴이/ })).toBeFocused();                 // Enter 를 반사적으로 눌러도 아무것도 켜지지 않는다
  // 목업의 문장 그대로
  await expect(card(page)).toContainText("문제가 생기면 알아서 바꾸고 알려요.");
  await expect(card(page)).toContainText("되돌릴 수 있어요.");
  await expect(card(page)).toContainText("끄고 진행하면 문제가 생길 때 먼저 물어봐요.");
  await expect(card(page)).toContainText("켜 두어도 고정한 일정은 먼저 물어봐요.");
  await expect(card(page)).toContainText("재난·지진이 나면 일정을 멈추고 안전 안내를 보내요.");
  await expect(card(page)).toContainText("켠 뒤에도 언제든 화면 위 아이콘에서 끌 수 있어요.");
  // 주 단추 둘은 크기가 같고 44px 이상이다
  const on = await card(page).getByRole("button", { name: "켜고 진행" }).boundingBox();
  const off = await card(page).getByRole("button", { name: "건너뛰기 — 끄고 진행" }).boundingBox();
  expect(on!.height).toBeGreaterThanOrEqual(44);
  expect(off!.height).toBeGreaterThanOrEqual(44);
  expect(Math.abs(on!.width - off!.width)).toBeLessThanOrEqual(1);
  expect(Math.abs(on!.height - off!.height)).toBeLessThanOrEqual(1);
  expect(await server.received("POST", "/v1/web/trip-intakes")).toHaveLength(0);
  // 뒤의 화면은 닿지 않는다
  expect(await page.locator("form").first().evaluate((element) => Boolean(element.closest("[inert]")))).toBe(true);
});

test("Esc · 닫기 단추 · 바깥을 눌러 닫으면 아무것도 정해지지 않고, 초점이 「계획 확인하기」로 돌아온다. Tab 은 카드 안에서만 돈다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page);
  await openRegistration(page);
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  for (const way of ["esc", "close", "outside"] as const) {
    await send(page).click();
    await expect(card(page)).toBeVisible();
    if (way === "esc") await page.keyboard.press("Escape");
    else if (way === "close") await card(page).getByRole("button", { name: "닫기" }).click();
    else await page.mouse.click(8, 8);
    await expect(card(page)).toHaveCount(0);
    await expect(send(page)).toBeFocused();
  }
  expect(await server.received("POST", "/v1/web/trip-intakes")).toHaveLength(0);
  // 머리줄 아이콘은 정하기 전에는 없다
  await expect(page.getByRole("button", { name: /항로 지킴이 (끄기|켜기)/ })).toHaveCount(0);
  // Tab 을 여러 번 눌러도 카드 밖으로 나가지 않는다
  await send(page).click();
  for (let i = 0; i < 6; i++) {
    await page.keyboard.press("Tab");
    expect(await page.evaluate(() => Boolean(document.activeElement?.closest('[role="dialog"]')))).toBe(true);
  }
  await page.keyboard.press("Shift+Tab");
  expect(await page.evaluate(() => Boolean(document.activeElement?.closest('[role="dialog"]')))).toBe(true);
});

test("좁은 화면(375×812)에서는 아래에서 올라오는 판으로 화면 안에 들어가고 단추는 44px 이상이다", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await start(page);
  await openRegistration(page);
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await send(page).click();
  await expect(card(page)).toBeVisible();
  await page.waitForTimeout(400);                                                                      // 올라오는 움직임이 끝난 뒤
  const box = await card(page).boundingBox();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(375);
  expect(box!.y + box!.height).toBeLessThanOrEqual(812 + 1);
  for (const name of ["켜고 진행", "건너뛰기 — 끄고 진행", "닫기"]) {
    const b = await card(page).getByRole("button", { name }).boundingBox();
    expect(b!.height).toBeGreaterThanOrEqual(44);
  }
});

test("「켜고 진행」은 on_disruption=replace, 「건너뛰기 — 끄고 진행」은 ask_first 를 **직접** 보낸다(안 보내는 것이 아니다)", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 0 });
  await start(page);
  await openRegistration(page);
  await fillPlanAsk(page, { start: weekAhead(), days: 2, party: 2 });
  await checkPlan(page, "건너뛰기 — 끄고 진행");
  await expect(page).toHaveURL(/\/trips\/[0-9a-f-]+$/, { timeout: 15_000 });
  const [plan] = await server.received("POST", "/plan");
  expect(plan.body).toMatchObject({ survey: { version: "2026-09-24.v1", pace: "moderate", on_disruption: "ask_first" } });

  await server.reset();
  await server.scenario({ readingPolls: 0 });
  await openRegistration(page);
  await fillPlanAsk(page, { start: weekAhead(), days: 2, party: 2 });
  await checkPlan(page, "켜고 진행");
  await expect(page).toHaveURL(/\/trips\/[0-9a-f-]+$/, { timeout: 15_000 });
  const [again] = await server.received("POST", "/plan");
  expect(again.body).toMatchObject({ survey: { on_disruption: "replace" } });
});

test("읽는 기준: 「적당히」가 처음부터 골라져 있고, 방향키로 옮기며(맨 끝에서 돌아 나온다), 고른 여유가 계획 짜기에 실려 간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ readingPolls: 0 });
  await start(page);
  await openRegistration(page);
  const group = page.getByRole("radiogroup", { name: "하루 일정의 여유" });
  const radio = (name: string) => group.getByRole("radio", { name });
  await expect(radio("적당히")).toHaveAttribute("aria-checked", "true");
  await expect(radio("여유롭게")).toHaveAttribute("aria-checked", "false");
  await expect(radio("적당히")).toHaveAttribute("tabindex", "0");
  await expect(radio("꽉 차게")).toHaveAttribute("tabindex", "-1");
  await radio("적당히").focus();
  await page.keyboard.press("ArrowRight");
  await expect(radio("꽉 차게")).toHaveAttribute("aria-checked", "true");
  await expect(radio("꽉 차게")).toBeFocused();
  await page.keyboard.press("ArrowRight");                                                             // 맨 끝에서 처음으로
  await expect(radio("여유롭게")).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await expect(radio("꽉 차게")).toBeFocused();
  await expect(group).not.toContainText(/\d+\s*(곳|개)/);                                              // 숫자 약속은 없다(「한 곳쯤」은 도움말에만)
  await fillPlanAsk(page, { start: weekAhead(), days: 2, party: 2 });
  await checkPlan(page);
  await expect(page).toHaveURL(/\/trips\/[0-9a-f-]+$/, { timeout: 15_000 });
  const [plan] = await server.received("POST", "/plan");
  expect(plan.body).toMatchObject({ survey: { pace: "packed", on_disruption: "replace" } });
});

test("머리줄 아이콘: 카드로 정한 뒤부터 보이고, 켜 둔 것을 누르면 바로 꺼지며 되돌리기 줄은 저절로 사라지지 않고, 꺼진 것을 누르면 카드(켜기 / 그대로 두기)가 열린다. 확정에는 마지막 선택이 간다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page);
  await openRegistration(page);
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await checkPlan(page);                                                                               // 켜고 진행
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);
  const toggle = (name: string) => page.getByRole("button", { name });
  await expect(toggle("항로 지킴이 끄기")).toBeVisible();
  await expect(toggle("항로 지킴이 끄기")).toContainText("지금 켜져 있어요");

  // 켜 둔 것을 누르면 확인 없이 바로 꺼진다 + 되돌리기 줄(저절로 사라지지 않는다)
  await toggle("항로 지킴이 끄기").click();
  await expect(toggle("항로 지킴이 켜기")).toBeVisible();
  const line = page.getByRole("status").filter({ hasText: "항로 지킴이를 껐어요. 문제가 생기면 물어볼게요." });
  await expect(line).toBeVisible();
  await page.waitForTimeout(5500);
  await expect(line).toBeVisible();
  // 되돌리기
  await line.getByRole("button", { name: "되돌리기" }).click();
  await expect(line).toHaveCount(0);
  await expect(toggle("항로 지킴이 끄기")).toBeVisible();

  // 다시 끄고, 꺼진 것을 누르면 카드: 「켜기」 / 「그대로 두기」(시작 때의 「끄고 진행하면…」 줄은 없다)
  await toggle("항로 지킴이 끄기").click();
  await line.getByRole("button", { name: "닫기" }).click();
  await expect(line).toHaveCount(0);
  await toggle("항로 지킴이 켜기").click();
  await expect(card(page)).toBeVisible();
  await expect(card(page).getByRole("button", { name: "켜기", exact: true })).toBeVisible();
  await expect(card(page).getByRole("button", { name: "그대로 두기" })).toBeVisible();
  await expect(card(page)).not.toContainText("끄고 진행하면 문제가 생길 때 먼저 물어봐요.");
  await card(page).getByRole("button", { name: "그대로 두기" }).click();
  await expect(card(page)).toHaveCount(0);
  await expect(toggle("항로 지킴이 켜기")).toBeVisible();                                                // 그대로 꺼져 있다

  // 꺼 둔 채로 등록하면 확정에는 ask_first 가 간다 (접수에는 아무 설문도 안 갔다)
  await page.getByRole("button", { name: "여행 등록" }).click();
  await expect(page).toHaveURL(/\/trips\/[0-9a-f-]+$/);
  const [confirm] = await server.received("POST", "/confirm");
  expect(confirm.body).toMatchObject({ survey: { on_disruption: "ask_first" } });
});

test("영어 화면에서도 아이콘 이름 · 되돌리기 줄이 영어로 나온다", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("tripilot.web.settings.v1", JSON.stringify({ language: "en", navigation: "fixed" })));
  await start(page);
  await openRegistration(page);
  await page.getByLabel("Your travel plan").fill(PLAN);
  await page.getByRole("button", { name: "Check my plan" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Turn on and go on" }).click();
  await page.getByRole("button", { name: "Turn Course Keeper off" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Course Keeper is off." })).toBeVisible();
  await expect(page.getByRole("button", { name: "Turn Course Keeper on" })).toBeVisible();
});
