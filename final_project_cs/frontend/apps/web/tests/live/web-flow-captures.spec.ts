import { expect, test } from "@playwright/test";
import { mockServer, start, checkPlan } from "./helpers";

for (const width of [375, 1280]) {
  test(`실제 화면 촬영과 가로 넘침 확인 ${width}px`, async ({ page, request }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    const mock = mockServer(request);
    await mock.reset();
    await mock.scenario({ questions: "two", readingPolls: 999, social: "on" });
    await start(page);
    const capture = async (name: string) => {
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
      await page.screenshot({ path: testInfo.outputPath(`${name}-${width}.png`), fullPage: true });
    };
    await page.goto("/trips/new");
    await page.getByLabel("나의 여행 계획").fill("10/1 09:00 경복궁 관람");
    await checkPlan(page);
    await page.getByLabel("직접 입력").fill("택시 + 버스");
    await capture("survey");
    await mock.scenario({ review: "on", board: "rich", readingPolls: 0 });
    await page.goto("/intakes/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee");
    await expect(page.locator('li[data-type="move"]').first().locator("[data-move-departure]")).toHaveText("10:30");
    await capture("validation");
    await page.locator("[data-insert-near] > button").click();
    await page.getByLabel("일정 이름", { exact: true }).fill("저녁 식사");
    await capture("add-stop");
    await page.goto("/mypage/account");
    await expect(page.getByRole("list", { name: "계정으로 계속하기" })).toBeVisible();
    await page.getByRole("list", { name: "계정으로 계속하기" }).scrollIntoViewIfNeeded();
    await capture("account");
  });
}
