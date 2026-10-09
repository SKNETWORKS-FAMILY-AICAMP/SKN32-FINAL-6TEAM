import { expect, test, type Page } from "@playwright/test";
import { mockServer } from "./helpers";
import { card, head, needsBadge, changedBadge, openFinished, pin, toast } from "./plan-check-kit";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });
const shot = async (page: Page, name: string) => {
  if (process.env.CONTINUITY_SHOTS) await page.screenshot({ path: `${process.env.CONTINUITY_SHOTS}/${name}.png`, fullPage: true });
};

test("정보 순서·아이콘 세 개·전체 복원은 한 흐름으로 동작한다", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  const api = await openFinished(page, request, undefined, { intakeEvents: "off" });
  await pin(page, "1. 경복궁 관람").dispatchEvent("click");
  const item = card(page, "경복궁 관람");
  const tools = item.locator("[class*=cardTools]");
  const buttons = tools.getByRole("button");
  await expect(buttons).toHaveCount(3);
  expect(await buttons.evaluateAll((nodes) => nodes.map((node) => node.getAttribute("aria-label")))).toEqual([
    "경복궁 관람 자동 추천", "경복궁 관람 수정", "경복궁 관람 삭제",
  ]);
  for (const button of await buttons.all()) {
    const box = (await button.boundingBox())!;
    expect(box.width).toBeGreaterThanOrEqual(44);
    expect(box.height).toBeGreaterThanOrEqual(44);
  }
  await buttons.nth(1).focus();
  await expect(buttons.nth(1).getByRole("tooltip")).toBeVisible();
  await head(page, "경복궁 관람").click();
  await expect(item.getByRole("button", { name: "경복궁 관람 수정", exact: true })).toHaveCount(1);
  await expect(item.getByRole("button", { name: "경복궁 관람 자동 추천", exact: true })).toHaveCount(1);
  await page.getByRole("button", { name: /^경복궁 관람 시간 고치기/ }).click();
  const form = page.getByRole("form", { name: "경복궁 관람 시간 고치기" });
  await form.getByLabel("끝", { exact: true }).fill("11:00");
  await form.getByRole("button", { name: "적용", exact: true }).click();
  await expect(changedBadge(page)).toHaveText("1");
  const allUndo = page.getByRole("button", { name: "전체 되돌리기", exact: true });
  await expect(allUndo).toBeVisible();
  await pin(page, "1. 경복궁 관람").dispatchEvent("click");
  const bar = page.getByRole("group", { name: "일정 확인과 변경" });
  await expect(bar.locator("[class*=picked]")).toContainText("경복궁 관람");
  const positions = await Promise.all([bar.locator("[class*=picked]"), needsBadge(page), changedBadge(page), allUndo].map((node) => node.boundingBox()));
  for (let i = 1; i < positions.length; i += 1) expect(positions[i]!.x).toBeGreaterThanOrEqual(positions[i - 1]!.x + positions[i - 1]!.width - 1);
  await toast(page, "1개 일정의 시간을 바꿨어요").getByRole("button", { name: "닫기", exact: true }).click();
  await shot(page, "01-status-and-actions-375");
  await allUndo.focus();
  await page.keyboard.press("Tab");
  await page.keyboard.press("Shift+Tab");
  await expect(allUndo).toBeFocused();
  await expect(allUndo.getByRole("tooltip")).toBeVisible();
  await allUndo.press("Enter");
  await expect(allUndo).toHaveCount(0);
  await expect(item.getByRole("img", { name: "변경 완료" })).toHaveCount(0);
  const restored = await api.received("POST", "/restore");
  expect(restored).toHaveLength(1);
  expect(restored[0].body).toEqual({ revision: 2, restore_revision: 1 });
  expect(await api.received("POST", "/edits")).toHaveLength(1);
});

test("저장 전 삭제만 있어도 전체 되돌리기로 취소하고 복원 API는 부르지 않는다", async ({ page, request }) => {
  const api = await openFinished(page, request, undefined, { intakeEvents: "off" });
  await pin(page, "1. 경복궁 관람").dispatchEvent("click");
  await card(page, "경복궁 관람").getByRole("button", { name: "경복궁 관람 삭제", exact: true }).click();
  await expect(card(page, "경복궁 관람")).toContainText("삭제 예정");
  await page.getByRole("button", { name: "전체 되돌리기", exact: true }).click();
  await expect(card(page, "경복궁 관람")).not.toContainText("삭제 예정");
  expect(await api.received("POST", "/restore")).toHaveLength(0);
  expect(await api.received("POST", "/edits")).toHaveLength(0);
});

for (const width of [375, 1280]) {
  test(`긴 제목·하단 연속 표면·수정안 미리 보기 (${width}px)`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    const title = "한국 전통 문화와 궁궐을 둘러보는 경복궁 관람";
    const api = await openFinished(page, request, (view) => { view.review.items[0].title = title; }, { intakeEvents: "off" });
    await pin(page, `1. ${title}`).dispatchEvent("click");
    const item = card(page, title);
    const titleBox = (await item.getByRole("heading").boundingBox())!;
    const toolsBox = (await item.locator("[class*=cardTools]").boundingBox())!;
    expect(titleBox.x + titleBox.width).toBeLessThanOrEqual(toolsBox.x + 1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await shot(page, `02-long-title-${width}`);
    const body = page.locator("div[class*=sheetBody]");
    await body.evaluate((element) => { element.scrollTop = element.scrollHeight; });
    const hint = body.locator("button[class*=pullHint]");
    await expect(hint).toContainText("내 취향에 맞게, 내 일정에 여유롭게.");
    await expect(hint).toContainText("아래로 스크롤하면 권장 수정안이 나와요");
    const hintBox = (await hint.boundingBox())!;
    const footerBox = (await page.locator("footer[class*=footer]").filter({ has: page.getByRole("button", { name: /^전체 자동 추천/ }) }).boundingBox())!;
    expect(Math.abs(footerBox.y - hintBox.y - hintBox.height)).toBeLessThanOrEqual(2);
    await shot(page, `03-bottom-continuity-${width}`);
    await hint.click();
    await expect(page.getByRole("group", { name: "보는 일정" })).toBeVisible();
    expect((await api.received("POST", "/autofix")).every((entry) => entry.body?.dry_run === true)).toBe(true);
    await shot(page, `04-proposed-${width}`);
  });
}
