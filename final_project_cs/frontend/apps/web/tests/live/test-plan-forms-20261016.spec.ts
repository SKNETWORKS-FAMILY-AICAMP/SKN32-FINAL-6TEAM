import { expect, test } from "@playwright/test";
import { readFileSync, mkdirSync } from "node:fs";
import { checkPlan, mockServer, noHorizontalScroll, start } from "./helpers";

// 2026-10-16 — 입력 형식별 테스트 계획(test17~50). 분류는 계획 이해 시험지(eval/intake_diverse)의 형식 이름 그대로다.
const catalog = JSON.parse(readFileSync(new URL("./fixtures/prepared-test-plans.json", import.meta.url), "utf8")) as { scenarios: { code: string; name: string; category: string; text: string; expected: string }[] };
const FORMS = ["정형 목록+자유 문장", "말투·오타 한 줄", "문단 자유문", "CSV·TSV", "JSON", "메모식 엑셀", "붙여 넣은 표", "나눠 보낸 메시지", "계획+질문+짜기", "중간 정정", "실제 접수"];

for (const width of [375, 1280]) {
  test(`${width}px 입력 형식 묶음이 검사 항목 묶음 뒤에 시험지 분류 이름으로 보이고, 고른 긴 계획은 코드로 제출된다`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 900 });
    const server = mockServer(request);
    await server.reset();
    await server.scenario({ readingPolls: 0, questions: "none" });
    await page.route("**/v1/web/test-scenarios", route => route.fulfill({ json: catalog }));
    await start(page);
    await page.goto("/trips/new");
    const picker = page.getByLabel("테스트 계획", { exact: true });
    await picker.click();
    const sections = page.locator("section[data-section]");
    await expect(sections).toHaveCount(2);
    await expect(sections.nth(0)).toHaveAttribute("data-section", "check");
    await expect(sections.nth(1)).toHaveAttribute("data-section", "form");
    await expect(sections.nth(1).locator("p").first()).toHaveText("입력 형식별 · 계획 이해 시험지 분류");
    await expect(sections.nth(1).locator("legend span[data-category]")).toHaveText(FORMS);
    await expect(sections.nth(1).locator("button[data-plan-code]")).toHaveCount(34);
    await expect(sections.nth(0).locator("button[data-plan-code]")).toHaveCount(16);
    const targets = await page.locator("button[data-plan-code]").evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().height));
    expect(targets.every(height => height >= 44)).toBe(true);
    await noHorizontalScroll(page);

    const long = catalog.scenarios.find(plan => plan.code === "test26")!;
    await page.locator('button[data-plan-code="test26"]').scrollIntoViewIfNeeded();
    mkdirSync("mockups/test-plan-forms-2026-10-16", { recursive: true });
    await page.screenshot({ path: `mockups/test-plan-forms-2026-10-16/list-${width}.png` });
    await page.locator('button[data-plan-code="test26"]').click();
    await expect(page.getByLabel("나의 여행 계획")).toHaveValue(long.text);
    await expect(picker).toContainText("문단 자유문");
    await expect(picker).toContainText("test26 · 김 · 4박 5일");
    await expect(page.getByRole("status").filter({ hasText: "10/16 지금 구조:" })).toBeVisible();
    await noHorizontalScroll(page);
    await page.screenshot({ path: `mockups/test-plan-forms-2026-10-16/selected-${width}.png` });
    await checkPlan(page);
    await expect.poll(async () => (await server.received("POST", "/v1/web/trip-intakes")).length).toBe(1);
    const sent = JSON.stringify((await server.received("POST", "/v1/web/trip-intakes"))[0]);
    expect(sent).toContain("test26");
    expect(sent).not.toContain("부모님 모시고");
  });
}

test("입력란에 test33처럼 적어도 입력 형식 계획으로 알아보고 분류 이름을 보여 준다", async ({ page, request }) => {
  await mockServer(request).reset();
  await page.route("**/v1/web/test-scenarios", route => route.fulfill({ json: catalog }));
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill(" TEST33 ");
  const picker = page.getByLabel("테스트 계획", { exact: true });
  await expect(picker).toContainText("test33 · 짧음 · 한 칸에 하루 통째");
  await expect(picker).toContainText("메모식 엑셀");
  await page.getByText("준비된 계획 원문 보기", { exact: true }).click();
  await expect(page.locator("details pre")).toContainText("오전 경복궁, 점심 통인시장");
  await page.getByLabel("나의 여행 계획").fill("test51");
  await expect(picker).toContainText("분류별 테스트 계획 선택");
});
