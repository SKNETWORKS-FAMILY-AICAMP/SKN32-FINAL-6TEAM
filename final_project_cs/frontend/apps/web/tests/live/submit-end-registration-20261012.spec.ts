import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { mockServer, noHorizontalScroll, start } from "./helpers";
import { INTAKE, mapSettled, patchIntake } from "./plan-check-kit";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

async function openResult(page: Page, request: APIRequestContext, kind: "ready" | "recheck" | "blocked" = "ready") {
  const api = mockServer(request);
  await api.scenario({ review: "on", board: "rich", readingPolls: 0, intakeEvents: "off" });
  if (kind !== "recheck") await patchIntake(page, view => {
    for (const entry of [...view.review.items, ...view.review.moves]) {
      entry.status = "keep";
      for (const row of entry.rows ?? []) row.result = "ok";
    }
    view.review.needs = { items: 0, moves: 0, total: 0 };
    view.review.ready = kind === "ready";
    view.check.ready = kind === "ready";
  });
  await start(page);
  await page.goto(`/intakes/${INTAKE}`);
  await expect(page.locator("[data-stage=done]")).toHaveCount(1);
  await expect(page.locator('[data-verdict="checking"]')).toHaveCount(0);
  await mapSettled(page);
  return api;
}

for (const width of [375, 1280]) for (const reduced of [false, true]) for (const kind of ["ready", "recheck"] as const) {
  test(`${width}px ${reduced ? "동작 줄임" : "일반"} ${kind}: 목록 끝에서 버튼 이름까지 즉시 표시`, async ({ page, request }, testInfo) => {
    await page.setViewportSize({ width, height: 812 });
    await page.emulateMedia({ reducedMotion: reduced ? "reduce" : "no-preference" });
    const api = await openResult(page, request, kind);
    const body = page.locator("div[class*=sheetBody]");
    const footer = page.locator("footer[class*=footer]");
    const tip = footer.getByRole("tooltip");
    await body.evaluate(element => { element.scrollTop = (element.scrollHeight - element.clientHeight) / 2; });
    await body.hover();
    await page.mouse.wheel(0, 10000);
    await expect.poll(() => body.evaluate(element => element.scrollHeight - element.clientHeight - element.scrollTop)).toBeLessThanOrEqual(2);
    await page.mouse.move(0, 0);
    await expect(footer).not.toHaveAttribute("data-quiet", { timeout: 250 });
    await expect(footer).not.toHaveAttribute("inert");
    await expect(tip).toHaveText(kind === "ready" ? "여행 등록" : "다시 제출");
    await expect(tip).toBeVisible({ timeout: 250 });
    await expect(tip).toHaveCSS("opacity", "1", { timeout: 250 });
    await body.hover();
    await page.mouse.wheel(0, 180);
    await page.mouse.move(0, 0);
    await expect(tip).toBeVisible({ timeout: 250 });
    await noHorizontalScroll(page);
    await page.screenshot({ path: testInfo.outputPath("bottom.png") });
    await body.hover();
    await page.mouse.wheel(0, -120);
    await page.mouse.move(0, 0);
    await expect(footer).toHaveAttribute("data-quiet", "true", { timeout: 250 });
    await expect(tip).toBeHidden();
    expect(await api.received("POST", "/confirm")).toHaveLength(0);
    expect(await api.received("POST", "/revalidate")).toHaveLength(0);
  });
}

test("등록 불가여도 끝에서는 안내를 표시하고 스크롤로는 전송하지 않는다", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  const api = await openResult(page, request, "blocked");
  const body = page.locator("div[class*=sheetBody]");
  const footer = page.locator("footer[class*=footer]");
  await body.evaluate(element => { element.scrollTop = element.scrollHeight; });
  await expect(footer.getByRole("tooltip")).toBeVisible({ timeout: 250 });
  await expect(footer.getByRole("button", { name: "여행 등록", exact: true })).toHaveAttribute("aria-disabled", "true");
  expect(await api.received("POST", "/confirm")).toHaveLength(0);
});

test("목록 끝에서도 최소 접힘 중에는 안내를 숨기고 펼치면 복귀한다", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await openResult(page, request);
  const body = page.locator("div[class*=sheetBody]");
  const footer = page.locator("footer[class*=footer]");
  await body.evaluate(element => { element.scrollTop = element.scrollHeight; });
  await expect(footer.getByRole("tooltip")).toBeVisible({ timeout: 250 });
  const handle = page.getByRole("button", { name: "목록 높이 바꾸기" });
  await handle.click();
  await handle.click();
  await expect(page.locator("[data-collapsed]")).toHaveCount(1);
  await expect(footer).toHaveAttribute("inert");
  await expect(footer.getByRole("tooltip")).toBeHidden();
  await handle.click();
  await expect(footer).not.toHaveAttribute("inert");
  // 펼치기는 기존 동작대로 목록 상단으로 돌아갈 수 있다. 다시 끝에 도착했을 때 안내를 확인한다.
  await body.evaluate(element => { element.scrollTop = element.scrollHeight; });
  await expect(footer.getByRole("tooltip")).toBeVisible();
});
