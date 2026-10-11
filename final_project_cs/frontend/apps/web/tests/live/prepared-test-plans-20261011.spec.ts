import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
const catalog = JSON.parse(readFileSync(new URL("./fixtures/prepared-test-plans.json", import.meta.url), "utf8")) as { enabled: boolean; scenarios: { code: string; name: string; description: string; text: string }[] };
import { checkPlan, mockServer, noHorizontalScroll, start } from "./helpers";

async function openPlans(page: Page) {
  await page.route("**/v1/web/test-scenarios", (route) => route.fulfill({ json: catalog }));
  await start(page);
  await page.goto("/trips/new");
}

for (const width of [375, 1280]) {
  test(`${width}px test1 직접 입력은 준비 원문을 표시하고 코드 한 번만 제출한다`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    const server = mockServer(request);
    await server.reset();
    await server.scenario({ readingPolls: 0, questions: "none" });
    await page.route("**/v1/web/trip-intakes/*", async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      if (body.intake_id && body.sources) body.test_scenario = catalog.scenarios[0];
      await route.fulfill({ response, json: body });
    });
    await openPlans(page);
    await page.getByLabel("나의 여행 계획").fill("  TEST1  ");
    await expect(page.getByLabel("테스트 계획", { exact: true })).toHaveValue("test1");
    await page.getByText("준비된 계획 원문 보기", { exact: true }).click();
    await expect(page.locator("details pre").filter({ hasText: "1일차 · 2026-10-18" })).toContainText("14:00~15:30 창덕궁 관람");
    await noHorizontalScroll(page);
    await page.getByLabel("테스트 계획", { exact: true }).scrollIntoViewIfNeeded();
    await page.screenshot({ path: test.info().outputPath(`prepared-test-${width}.png`) });
    await checkPlan(page);
    await expect(page.getByRole("article", { name: "경복궁 관람" })).toBeVisible();
    await expect(page.getByRole("note").filter({ hasText: "시험 계획 test1" })).toBeVisible();
    const posts = await server.received("POST", "/v1/web/trip-intakes");
    expect(posts).toHaveLength(1);
    expect(JSON.stringify(posts[0])).toContain("TEST1");
    await noHorizontalScroll(page);
  });

  test(`${width}px 목록 선택은 입력을 바꾸고 다른 글을 입력하면 시험 선택을 해제한다`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    await mockServer(request).reset();
    await openPlans(page);
    const select = page.getByLabel("테스트 계획", { exact: true });
    await select.selectOption("test12");
    await expect(page.getByLabel("나의 여행 계획")).toHaveValue("test12");
    await expect(page.getByRole("status").filter({ hasText: "서울의 활동·식사·이동" })).toBeVisible();
    await page.getByLabel("나의 여행 계획").fill("test1을 참고해서 서울을 여행할 거예요");
    await expect(select).toHaveValue("");
    await expect(page.getByText("준비된 계획 원문 보기", { exact: true })).toHaveCount(0);
    await noHorizontalScroll(page);
  });
}

test("시험 목록 오류는 일반 글 입력·전송을 막지 않고 다시 불러올 수 있다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.reset();
  await server.scenario({ readingPolls: 0, questions: "none" });
  await page.route("**/v1/web/test-scenarios", (route) => route.fulfill({ status: 503, json: { detail: { code: "unavailable", message: "목록 조회 실패" } } }));
  await start(page);
  await page.goto("/trips/new");
  await expect(page.getByRole("button", { name: "다시 불러오기", exact: true })).toBeVisible();
  await page.getByLabel("나의 여행 계획").fill("10/18 09:00 경복궁 관람");
  await checkPlan(page);
  await expect(page.getByRole("article", { name: "경복궁 관람" })).toBeVisible();
  expect(await server.received("POST", "/v1/web/trip-intakes")).toHaveLength(1);
});

test("꺼진 시험 목록은 준비된 선택지를 표시하지 않는다", async ({ page, request }) => {
  await mockServer(request).reset();
  await page.route("**/v1/web/test-scenarios", (route) => route.fulfill({ json: { enabled: false, scenarios: [] } }));
  await start(page);
  await page.goto("/trips/new");
  await expect(page.getByText("시험 일정 입력이 꺼져 있어요.", { exact: true })).toBeVisible();
  await expect(page.getByLabel("테스트 계획", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("나의 여행 계획")).toBeEnabled();
});
