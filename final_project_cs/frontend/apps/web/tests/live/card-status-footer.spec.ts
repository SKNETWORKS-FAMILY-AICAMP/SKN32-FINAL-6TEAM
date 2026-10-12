import { expect, test, type Page } from "@playwright/test";
import { mockServer } from "./helpers";
import { card, head, openFinished, pin, toast } from "./plan-check-kit";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });
const shot = async (page: Page, name: string) => {
  if (process.env.CARD_FOOTER_SHOTS) await page.screenshot({ path: `${process.env.CARD_FOOTER_SHOTS}/${name}.png`, fullPage: true });
};

test("확인 필요는 접힌 카드와 펼친 카드의 오른쪽 아래에 놓인다", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await openFinished(page, request, undefined, { intakeEvents: "off" });
  const item = card(page, "올리브영");
  const warning = item.getByText("확인 필요", { exact: true });
  const lowerRight = async () => {
    const box = (await item.boundingBox())!;
    const badge = (await warning.boundingBox())!;
    const title = (await item.getByRole("heading").boundingBox())!;
    expect(badge.y).toBeGreaterThan(title.y + title.height - 1);
    expect(box.x + box.width - badge.x - badge.width).toBeLessThan(16);
    expect(box.y + box.height - badge.y - badge.height).toBeLessThan(16);
  };
  await warning.scrollIntoViewIfNeeded();
  await lowerRight();
  await head(page, "올리브영").click();
  await expect(head(page, "올리브영")).toHaveAttribute("aria-expanded", "true");
  await lowerRight();
  await shot(page, "01-review-bottom-right-mobile");
});

test("시간 변경은 제목 옆 체크만 보이고 되돌리기는 펼친 카드 맨 아래 오른쪽에 남는다", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  const server = await openFinished(page, request, undefined, { intakeEvents: "off" });
  await page.getByRole("button", { name: /^경복궁 관람 시간 고치기/ }).click();
  const form = page.getByRole("form", { name: "경복궁 관람 시간 고치기" });
  await form.getByLabel("끝", { exact: true }).fill("11:00");
  await form.getByRole("button", { name: "적용" }).click();
  const item = card(page, "경복궁 관람");
  await expect(item.getByRole("img", { name: "변경 완료" })).toBeVisible();
  await expect(item).not.toContainText("변경 완료");
  const title = (await item.locator("[id^=plan-item-]").first().boundingBox())!;
  const mark = (await item.getByRole("img", { name: "변경 완료" }).boundingBox())!;
  expect(mark.x - title.x - title.width).toBeGreaterThanOrEqual(3);
  expect(mark.x - title.x - title.width).toBeLessThanOrEqual(5);
  if (await head(page, "경복궁 관람").getAttribute("aria-expanded") !== "true") await head(page, "경복궁 관람").click();
  const undo = item.getByRole("button", { name: "경복궁 관람 시간 되돌리기" });
  await undo.scrollIntoViewIfNeeded();
  const box = (await item.boundingBox())!;
  const button = (await undo.boundingBox())!;
  expect(button.height).toBeGreaterThanOrEqual(44);
  expect(box.x + box.width - button.x - button.width).toBeLessThan(16);
  expect(box.y + box.height - button.y - button.height).toBeLessThan(16);
  await toast(page, "1개 일정의 시간을 바꿨어요").getByRole("button", { name: "닫기", exact: true }).click();
  await shot(page, "02-time-undo-bottom-right-mobile");
  await undo.focus();
  await undo.press("Enter");
  await expect(item.getByRole("img", { name: "변경 완료" })).toHaveCount(0);
  await expect(undo).toHaveCount(0);
  const edits = await server.received("POST", "/edits");
  expect(edits.at(-1)!.body!.edits).toContainEqual({ source_id: "s1", field: "items[0].ends_at", value: "10:30" });
});

for (const reducedMotion of ["no-preference", "reduce"] as const) {
  test(`출처는 한 줄로 접히고 키보드로 펼쳐지며 일차 전환 후 복귀한다 (${reducedMotion})`, async ({ page, request }) => {
    await page.setViewportSize({ width: 514, height: 715 });
    await page.emulateMedia({ reducedMotion });
    await openFinished(page, request, (view) => {
      view.review.items.push({ ...view.review.items[0], id: "0-3", index: 3, title: "N서울타워", day: 2, date: "2026-10-02" });
    }, { intakeEvents: "off", intakeRoutes: "on" });
    const credit = page.locator("details[class*=credit]");
    const summary = credit.locator("summary");
    await summary.scrollIntoViewIfNeeded();
    await expect(summary).toContainText("ⓒ한국관광공사");
    await expect(summary).toContainText("© OpenStreetMap");
    await expect(credit.getByRole("link", { name: "저작권 정책" })).not.toBeVisible();
    await summary.focus();
    await summary.press("Enter");
    await expect(credit.getByRole("link", { name: "저작권 정책" })).toBeVisible();
    await expect(credit).toContainText("OpenStreetMap contributors (ODbL)");
    await expect(credit.locator("[data-route-note]").first()).toBeVisible();
    await shot(page, `05-expanded-source-${reducedMotion}`);
    await summary.press("Enter");
    await summary.evaluate((element) => element.blur());
    await shot(page, `03-compact-source-${reducedMotion}`);
    const observed: boolean[] = [];
    await page.exposeFunction("sourceVisibilitySample", (hidden: boolean) => observed.push(hidden));
    await credit.evaluate((element) => {
      new MutationObserver(() => {
        const send = (window as unknown as { sourceVisibilitySample: (hidden: boolean) => void }).sourceVisibilitySample;
        send(element.hasAttribute("data-muted") && element.hasAttribute("inert"));
      }).observe(element, { attributes: true, attributeFilter: ["data-muted"] });
    });
    await expect(page.getByRole("tablist", { name: "일차 고르기" })).toHaveCSS("opacity", "1");
    await expect(page.getByRole("tablist", { name: "일차 고르기" })).not.toHaveAttribute("inert", "");
    await page.getByRole("tab", { name: /2일차/ }).click();
    await expect(card(page, "N서울타워")).toBeVisible();
    await expect(credit).not.toHaveAttribute("data-muted", "true");
    await expect.poll(() => observed.includes(true)).toBe(true);
    await expect(credit).not.toHaveAttribute("inert", "");
    await summary.scrollIntoViewIfNeeded();
    await expect(summary).toHaveCSS("opacity", "1");
    // 수정안 앞뒤 전환은 일차 이동과 다른 애니메이션이며, 여기서도 안내가 겹치지 않고 복귀해야 한다.
    observed.length = 0;
    await page.getByRole("button", { name: /^전체 자동 추천/ }).click();
    await expect(page.getByRole("group", { name: "보는 일정" })).toBeVisible();
    await expect.poll(() => observed.includes(true)).toBe(true);
    await expect(credit).not.toHaveAttribute("data-muted", "true");
    observed.length = 0;
    await page.getByRole("button", { name: "1. 변경 전 일정" }).click();
    await expect.poll(() => observed.includes(true)).toBe(true);
    await expect(credit).not.toHaveAttribute("data-muted", "true");
  });
}

test("긴 일정 제목과 카드 상태는 휴대폰과 PC 화면에서 겹치지 않는다", async ({ page, request }) => {
  const title = "한국 전통 문화와 궁궐을 둘러보는 경복궁 관람";
  await page.setViewportSize({ width: 375, height: 812 });
  await openFinished(page, request, (view) => { view.review.items[0].title = title; }, { intakeEvents: "off" });
  for (const width of [375, 1280]) {
    await page.setViewportSize({ width, height: 812 });
    await pin(page, `1. ${title}`).dispatchEvent("click");
    await expect(card(page, title)).toBeVisible();
    const [item, heading] = [await card(page, title).boundingBox(), await card(page, title).getByRole("heading").boundingBox()];
    expect(heading!.x).toBeGreaterThanOrEqual(item!.x);
    expect(heading!.x + heading!.width).toBeLessThanOrEqual(item!.x + item!.width);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await shot(page, `04-long-title-${width}`);
  }
});
