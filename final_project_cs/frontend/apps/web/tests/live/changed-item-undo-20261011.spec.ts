import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { mockServer, noHorizontalScroll, start } from "./helpers";

const intake = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const gallery = "mockups/changed-item-undo-2026-10-11-v1";

async function open(page: Page, request: APIRequestContext) {
  const server = mockServer(request);
  await server.reset();
  await server.scenario({ review: "on", board: "rich", readingPolls: 0, questions: "none" });
  await start(page);
  await page.goto(`/intakes/${intake}`);
  await expect(page.locator("#plan-card-0-1")).toBeVisible();
  return server;
}

async function recommend(page: Page, id: string) {
  const card = page.locator(`#plan-card-${id}`);
  const head = card.getByRole("heading").getByRole("button");
  if (await head.getAttribute("aria-expanded") !== "true") await head.click();
  await page.locator(`#plan-recommend-${id}`).click();
  await expect(card.getByRole("button", { name: /변경 되돌리기$/ })).toBeVisible();
  await expect(page.locator(`#plan-recommend-${id}`)).toHaveCount(0);
}

for (const width of [375, 1280]) {
  test(`${width}px 변경한 일정은 추천 대신 되돌리기를 표시하고 그 일정만 복원한다`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 900 });
    const server = await open(page, request);
    const card = page.locator("#plan-card-0-1");
    const original = await card.getByRole("heading").innerText();
    await recommend(page, "0-1");
    await noHorizontalScroll(page);
    await mkdir(gallery, { recursive: true });
    await page.screenshot({ path: `${gallery}/changed-${width}.png` });
    await card.screenshot({ path: `${gallery}/card-changed-${width}.png` });
    // Change a second stop: restoring the first must not invoke whole-plan undo.
    await recommend(page, "0-0");
    const undo = card.getByRole("button", { name: /변경 되돌리기$/ });
    if (width === 1280) { await undo.focus(); await page.keyboard.press("Enter"); }
    else await undo.click();
    await expect(card.getByRole("heading")).toHaveText(original);
    await expect(card.getByRole("button", { name: /변경 되돌리기$/ })).toHaveCount(0);
    await expect(page.locator("#plan-card-0-0").getByRole("button", { name: /변경 되돌리기$/ })).toBeVisible();
    const restores = await server.received("POST", "/restore");
    expect(restores).toHaveLength(1);
    expect(restores[0].body?.item).toEqual({ source_id: "s1", index: 1 });
    await noHorizontalScroll(page);
    await page.screenshot({ path: `${gallery}/restored-${width}.png` });
    await card.screenshot({ path: `${gallery}/card-restored-${width}.png` });
  });
}

test("복원 실패는 변경과 되돌리기를 유지하며 다시 누르면 복원한다", async ({ page, request }) => {
  await open(page, request);
  await recommend(page, "0-1");
  const card = page.locator("#plan-card-0-1");
  const changed = await card.getByRole("heading").innerText();
  const restore = `**/v1/web/trip-intakes/${intake}/restore`;
  await page.route(restore, route => route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ error: { code: "schedule_check_failed", message: "일정 확인을 마치지 못했어요. 다시 시도해 주세요." } }) }));
  await card.getByRole("button", { name: /변경 되돌리기$/ }).click();
  await expect(page.getByRole("alert").filter({ hasText: "일정 확인을 마치지 못했어요" })).toBeVisible();
  await expect(card.getByRole("heading")).toHaveText(changed, { useInnerText: true });
  await expect(card.getByRole("button", { name: /변경 되돌리기$/ })).toBeEnabled();
  await expect(page.locator("#plan-recommend-0-1")).toHaveCount(0);
  await page.unroute(restore);
  await card.getByRole("button", { name: /변경 되돌리기$/ }).click();
  await expect(card.getByRole("button", { name: /변경 되돌리기$/ })).toHaveCount(0);
});
