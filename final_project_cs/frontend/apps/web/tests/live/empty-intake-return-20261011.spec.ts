import { expect, test } from "@playwright/test";
import { checkPlan, mockServer, noHorizontalScroll, start } from "./helpers";

const notice = "일정을 찾지 못했어요. 날짜·시간·장소를 확인해 다시 입력하거나 파일을 올려 주세요.";
const source = "서울 여행을 가려고 해요. 아직 방문 날짜와 장소는 정하지 않았어요.";

for (const width of [375, 1280]) {
  test(`${width}px 읽는 중 0개는 기다리고 완료 0개는 질문 유지보다 먼저 입력으로 돌아가 글을 고쳐 다시 보낸다`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    const server = mockServer(request);
    await server.reset();
    await server.scenario({ intake: "empty_plan", questions: "two", readingPolls: 999 });
    await start(page);
    let release!: () => void;
    const ready = new Promise<void>((resolve) => { release = resolve; });
    await page.route("**/v1/web/trip-intakes/*/events", async (route) => {
      await ready;
      await route.fulfill({ contentType: "text/event-stream", body: 'event: result\ndata: {"state":{"status":"review","stage":"review","revision":1}}\n\n' });
    });
    await page.goto("/trips/new");
    await page.getByLabel("나의 여행 계획").fill(source);
    await checkPlan(page);
    const questions = page.getByRole("region", { name: "질문 2개" });
    await expect(questions).toBeVisible();
    await questions.getByRole("button", { name: "택시", exact: true }).click();
    await expect(page.getByText("찾은 일정", { exact: false })).toContainText("0");
    await page.waitForTimeout(600);
    await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]{36}$/);
    await server.scenario({ readingPolls: 0 });
    release();
    await expect(page).toHaveURL(/\/trips\/new$/, { timeout: 5000 });
    await expect(page.locator("#plan-error")).toHaveText(notice);
    await expect(page.getByLabel("나의 여행 계획")).toHaveValue(source);
    await expect(questions).toHaveCount(0);
    await noHorizontalScroll(page);
    await page.screenshot({ path: test.info().outputPath(`empty-return-${width}.png`) });
    expect(await server.received("POST", "/v1/web/trip-intakes")).toHaveLength(1);
    await server.scenario({ intake: "items", questions: "none" });
    await page.getByLabel("나의 여행 계획").fill("10/15 09:00 경복궁 관람");
    await expect(page.locator("#plan-error")).toHaveCount(0);
    await checkPlan(page);
    await expect(page.getByRole("article", { name: "경복궁 관람" })).toBeVisible();
    expect(await server.received("POST", "/v1/web/trip-intakes")).toHaveLength(2);
  });

  test(`${width}px 파일에서 일정 0개면 입력 화면에 선택 파일을 복원하고 재전송하지 않는다`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    const server = mockServer(request);
    await server.reset();
    await server.scenario({ intake: "empty_plan", questions: "none", readingPolls: 0 });
    await start(page);
    await page.goto("/trips/new");
    await page.locator("#plan-files").setInputFiles({ name: "서울여행-메모.txt", mimeType: "text/plain", buffer: Buffer.from(source) });
    await checkPlan(page);
    await expect(page.locator("#plan-error")).toHaveText(notice);
    await expect(page).toHaveURL(/\/trips\/new$/);
    await expect(page.getByRole("list", { name: "선택한 파일" })).toContainText("서울여행-메모.txt");
    await expect(page.locator('[data-pane="files"]')).toHaveAttribute("data-active", "true");
    await page.waitForTimeout(600);
    expect(await server.received("POST", "/v1/web/trip-intakes")).toHaveLength(1);
    await noHorizontalScroll(page);
  });
}
