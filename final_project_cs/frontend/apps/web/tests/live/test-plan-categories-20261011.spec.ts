import { expect, test } from "@playwright/test";
import { readFileSync, mkdirSync } from "node:fs";
import { mockServer, noHorizontalScroll, start, checkPlan } from "./helpers";

const catalog = JSON.parse(readFileSync(new URL("./fixtures/prepared-test-plans.json", import.meta.url), "utf8"));

for (const width of [375, 1280]) {
  test(`${width}px 분류 색·기본안 우선·키보드 선택과 새 코드 제출`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 900 });
    const server = mockServer(request);
    await server.reset();
    await server.scenario({ readingPolls: 0, questions: "none" });
    await page.route("**/v1/web/test-scenarios", route => route.fulfill({ json: catalog }));
    await start(page);
    await page.goto("/trips/new");
    const picker = page.getByLabel("테스트 계획", { exact: true });
    await picker.click();
    await expect(page.locator("button[data-plan-code]")).toHaveCount(50);
    await expect(page.locator("button[data-plan-code]").first()).toHaveAttribute("data-plan-code", "test13");
    const firstOption = page.locator('button[data-plan-code="test13"]');
    await expect(firstOption).toBeInViewport();
    await expect(page.locator("fieldset").filter({ has: page.locator('button[data-plan-code="test13"]') })).toContainText("문제 없는 기본안");
    const colors = await page.locator('legend span[data-category]').evaluateAll(nodes => nodes.map(node => getComputedStyle(node).backgroundColor));
    expect(new Set(colors).size).toBe(7);
    const targets = await page.locator("button[data-plan-code]").evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().height));
    expect(targets.every(height => height >= 44)).toBe(true);
    await noHorizontalScroll(page);
    await picker.locator("..").scrollIntoViewIfNeeded();
    mkdirSync("mockups/test-plan-categories-2026-10-11-v1", { recursive: true });
    await page.screenshot({ path: `mockups/test-plan-categories-2026-10-11-v1/list-${width}.png` });
    await picker.press("ArrowDown");
    await expect(page.locator('button[data-plan-code="test13"]')).toBeFocused();
    await page.keyboard.press("ArrowDown");
    await expect(page.locator('button[data-plan-code="test14"]')).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(picker).toBeFocused();
    await expect(page.locator("button[data-plan-code]").first()).not.toBeVisible();
    await picker.press("Enter");
    await picker.press("ArrowUp");
    await expect(page.locator('button[data-plan-code="test50"]')).toBeFocused();
    await page.keyboard.press("Home");
    await expect(page.locator('button[data-plan-code="test13"]')).toBeFocused();
    await page.keyboard.press("End");
    await expect(page.locator('button[data-plan-code="test50"]')).toBeFocused();
    await page.keyboard.press("Escape");
    await picker.press("Enter");
    await picker.press("ArrowDown");
    await page.keyboard.press("Enter");
    await expect(page.getByLabel("나의 여행 계획")).toHaveValue(catalog.scenarios.find((plan: { code: string }) => plan.code === "test13").text);
    await expect(picker).toContainText("문제 없는 기본안");
    await expect(picker).toBeFocused();
    await page.getByText("준비된 계획 원문 보기", { exact: true }).click();
    await expect(page.locator("pre")).toContainText("14:00~15:00 인사동");
    await noHorizontalScroll(page);
    await page.screenshot({ path: `mockups/test-plan-categories-2026-10-11-v1/selected-${width}.png` });
    await checkPlan(page);
    await expect.poll(async () => (await server.received("POST", "/v1/web/trip-intakes")).length).toBe(1);
    const posts = await server.received("POST", "/v1/web/trip-intakes");
    expect(posts).toHaveLength(1);
    expect(JSON.stringify(posts[0])).toContain("test13");
  });
}

test("직접 입력 test14·test15와 구버전 분류 없는 응답도 선택된다", async ({ page, request }) => {
  await mockServer(request).reset();
  await page.route("**/v1/web/test-scenarios", route => route.fulfill({ json: catalog }));
  await start(page);
  await page.goto("/trips/new");
  for (const code of ["test14", "test15"]) {
    await page.getByLabel("나의 여행 계획").fill(code);
    await expect(page.getByLabel("테스트 계획", { exact: true })).toContainText(`${code} ·`);
    await expect(page.getByLabel("테스트 계획", { exact: true })).toContainText("문제 없는 기본안");
  }
  const oldCatalog = { ...catalog, scenarios: catalog.scenarios.map((entry: { category?: string; code: string }) => { const copy = { ...entry }; delete copy.category; return copy; }) };
  await page.route("**/v1/web/test-scenarios", route => route.fulfill({ json: oldCatalog }));
  await page.reload();
  await page.getByLabel("나의 여행 계획").fill("test1");
  await expect(page.getByLabel("테스트 계획", { exact: true })).toContainText("일반 흐름");
});
