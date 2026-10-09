import { expect, test } from "@playwright/test";
import { mockServer, start } from "./helpers";
import { card, INTAKE, mapSettled, openFinished, pin } from "./plan-check-kit";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });
const shot = async (page: import("@playwright/test").Page, name: string) => {
  if (process.env.LOADING_SHOTS) await page.screenshot({ path: `${process.env.LOADING_SHOTS}/${name}.png`, fullPage: true });
};

test("마커로 연 일정의 윗부분은 전체·일차 줄 아래에 놓인다", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await openFinished(page, request, (view) => {
    view.review.items.push({ ...view.review.items[0], id: "0-3", index: 3, title: "N서울타워", day: 2, date: "2026-10-02" });
  }, { intakeEvents: "off" });
  await expect(page.getByRole("tablist", { name: "일차 고르기" })).toBeVisible();
  const belowHeader = async (title: string) => {
    await expect.poll(async () => {
      const row = await card(page, title).boundingBox();
      const heading = await card(page, title).getByRole("heading").boundingBox();
      const head = await page.locator("header[class*=sheetHead]").boundingBox();
      const body = await page.locator("div[class*=sheetBody]").boundingBox();
      if (!row || !heading || !head || !body) return false;
      const gap = row.y - head.y - head.height;
      return gap >= 10 && gap <= 20 && heading.y >= head.y + head.height && heading.y + heading.height <= body.y + body.height;
    }).toBe(true);
    await expect(page.getByRole("tablist", { name: "일차 고르기" })).not.toHaveAttribute("data-quiet", "true");
    await expect(page.getByRole("tablist", { name: "일차 고르기" })).toHaveCSS("opacity", "1");
  };
  for (const [label, title] of [["3. 광장시장", "광장시장"], ["1. 경복궁 관람", "경복궁 관람"], ["3. 광장시장", "광장시장"]]) {
    await mapSettled(page);
    await pin(page, label).locator("[data-pin-body]").click();
    await expect(pin(page, label)).toHaveAttribute("aria-pressed", "true");
    await belowHeader(title);
  }
  await shot(page, "06-marker-below-days");
});

test("검증 중 마지막 일정은 목록 가운데에 따라오고 지도 마커도 함께 보인다", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  const server = mockServer(request);
  await server.scenario({ readingPolls: 99, intakeEvents: "off", review: "on", board: "rich" });
  await start(page);
  await page.goto(`/intakes/${INTAKE}`);
  await expect(page.locator('[data-stage="reading"]')).toBeVisible();
  await server.scenario({ readingPolls: 0 });
  const body = page.locator("div[class*=sheetBody]");
  await expect.poll(async () => body.locator("li[data-type=item]").count()).toBeGreaterThanOrEqual(2);
  await expect.poll(async () => {
    if (await page.locator('[data-stage="done"]').count()) return 999;
    const box = await body.boundingBox();
    const row = await body.locator("li[data-type]").last().boundingBox();
    return box && row ? Math.abs(row.y + row.height / 2 - box.y - box.height / 2) : 999;
  }, { intervals: [50], timeout: 5000 }).toBeLessThan(22);
  await expect(page.getByRole("region", { name: "여행 지도" })).toBeVisible();
  await expect(page.locator("[data-pin-body]").first()).toBeVisible();
  await shot(page, "07-check-centered");
});

test("목록을 접은 상태에서 마커를 다시 열어도 긴 제목은 일차 줄 아래에 보인다", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  const title = "한국 전통 문화와 궁궐을 둘러보는 경복궁 관람";
  await openFinished(page, request, (view) => {
    view.review.items[0].title = title;
    view.review.items.push({ ...view.review.items[0], id: "0-3", index: 3, title: "N서울타워", day: 2, date: "2026-10-02" });
  }, { intakeEvents: "off" });
  const root = page.locator("div[data-sheet]");
  for (let tries = 0; tries < 3 && await root.getAttribute("data-sheet") !== "peek"; tries++) {
    await page.getByRole("button", { name: "목록 높이 바꾸기" }).click();
  }
  await expect(root).toHaveAttribute("data-sheet", "peek");
  for (let attempt = 0; attempt < 2; attempt++) {
    await mapSettled(page);
    await pin(page, `1. ${title}`).locator("[data-pin-body]").click();
    await expect(root).toHaveAttribute("data-sheet", "half");
    await expect.poll(async () => {
      const heading = await card(page, title).getByRole("heading").boundingBox();
      const header = await page.locator("header[class*=sheetHead]").boundingBox();
      const body = await page.locator("div[class*=sheetBody]").boundingBox();
      return Boolean(heading && header && body && heading.y >= header.y + header.height + 10 && heading.y + heading.height <= body.y + body.height);
    }).toBe(true);
    if (attempt === 0) {
      await mapSettled(page);
      await pin(page, `1. ${title}`).locator("[data-pin-body]").click();
      await expect(pin(page, `1. ${title}`)).toHaveAttribute("aria-pressed", "false");
    }
  }
});
