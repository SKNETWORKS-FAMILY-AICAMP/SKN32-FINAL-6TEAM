import { expect, test, type Page } from "@playwright/test";
import { mkdir, access } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { mockServer, start, noHorizontalScroll } from "./helpers";
import { openFinished, head, pin, toast } from "./plan-check-kit";
import { useMapTiles } from "./capture-map-tiles";

const output = process.env.COMPACT_UI_SHOTS;
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });
async function capture(page: Page, name: string) {
  if (!output) return;
  await mkdir(output, { recursive: true });
  await page.mouse.move(0, 0); await page.waitForTimeout(220);
  await page.screenshot({ path: `${output}/${name}.png`, fullPage: true });
}
async function separate(page: Page) {
  return page.getByRole("region", { name: "여행 지도" }).evaluate((map) => {
    const r = map.getBoundingClientRect();
    const nodes = [...map.querySelectorAll<HTMLElement>("[data-pin-body], [data-edge-chip], [data-map-controls], [data-route-label]")];
    const boxes = nodes.filter((node) => getComputedStyle(node).visibility !== "hidden" && getComputedStyle(node).display !== "none")
      .map((node) => ({ name: node.dataset.pinBody !== undefined ? `마커 ${node.textContent}` : node.dataset.edgeChip !== undefined ? `거리 ${node.textContent}` : node.dataset.routeLabel !== undefined ? `경로 ${node.textContent}` : "지도 단추", box: node.getBoundingClientRect() }))
      .filter(({ box }) => box.right > r.left && box.left < r.right && box.bottom > r.top && box.top < r.bottom);
    const collisions: string[] = [];
    boxes.forEach((one, at) => boxes.slice(at + 1).forEach((other) => {
      if (Math.min(one.box.right, other.box.right) - Math.max(one.box.left, other.box.left) > 1 && Math.min(one.box.bottom, other.box.bottom) - Math.max(one.box.top, other.box.top) > 1) collisions.push(`${one.name} / ${other.name}`);
    }));
    return collisions;
  });
}
for (const width of [375, 1280]) {
  test(`지도·카드·플로팅 제출·하단 연결 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    const tiles = output ? await useMapTiles(page) : async () => {};
    await openFinished(page, request, undefined, { intakeEvents: "off", intakeRoutes: "on" });
    await tiles();
    await page.waitForTimeout(400);
    const tools = page.getByRole("group", { name: "지도 단추" });
    await expect(tools.getByRole("button", { name: "지도 단추 펼치기" })).toBeVisible();
    await expect(tools.getByRole("img", { name: /^거리 눈금/ })).toBeVisible();
    await expect(tools.getByRole("button", { name: "확대", exact: true })).toHaveCount(0);
    await expect.poll(() => separate(page)).toEqual([]);
    const fab = page.getByRole("button", { name: "다시 제출", exact: true });
    const box = (await fab.boundingBox())!;
    expect(box.width).toBe(56); expect(box.height).toBe(56);
    await expect(page.getByRole("button", { name: /전체 자동 추천/ })).toHaveCount(1);
    expect(await page.locator("div[class*=sheetBody]").getByRole("button", { name: /전체 자동 추천/ }).count()).toBe(1);
    const heading = page.getByRole("heading", { name: "계획 확인", exact: true });
    await expect(heading).toHaveClass("sr-only");
    const intro = toast(page, "계획 확인 화면이에요");
    await expect(intro).toHaveCount(0);
    await pin(page, "1. 경복궁 관람").dispatchEvent("click");
    await page.getByRole("button", { name: /^경복궁 관람 시간 고치기/ }).click();
    const time = page.getByRole("form", { name: "경복궁 관람 시간 고치기" });
    await time.getByLabel("끝", { exact: true }).fill("11:00");
    await time.getByRole("button", { name: "적용", exact: true }).click();
    await expect(page.getByRole("button", { name: "전체 되돌리기", exact: true })).toBeVisible();
    await toast(page, "1개 일정의 시간을 바꿨어요").getByRole("button", { name: "닫기", exact: true }).click();
    await expect.poll(() => separate(page)).toEqual([]);
    await capture(page, `01-compact-status-${width}`);
    await tools.getByRole("button", { name: "지도 단추 펼치기" }).click();
    for (let i = 0; i < 3; i++) { await tools.getByRole("button", { name: "확대", exact: true }).click(); await page.waitForTimeout(300); }
    await page.waitForTimeout(400);
    await expect.poll(() => separate(page)).toEqual([]);
    await expect(page.locator("[data-edge-chip]").first()).toBeVisible();
    await capture(page, `02-edge-chips-${width}`);
    await tools.getByRole("button", { name: "모든 일정 보기" }).click();
    await page.getByRole("button", { name: "전체 되돌리기", exact: true }).click();
    const body = page.locator("div[class*=sheetBody]");
    await body.evaluate((node) => { node.scrollTop = node.scrollHeight; });
    const down = page.getByRole("button", { name: "아래로 스크롤하면 권장 수정안이 나와요", exact: true });
    await expect(down).toBeVisible();
    expect((await down.boundingBox())!.height).toBeLessThanOrEqual(56);
    await capture(page, `03-bottom-${width}`);
    await down.click();
    const up = page.getByRole("button", { name: "계속 올리면 변경 전 일정이에요", exact: true });
    await expect(up).toBeVisible();
    expect((await up.boundingBox())!.height).toBeLessThanOrEqual(56);
    const notice = page.getByRole("status").filter({ has: page.getByRole("button", { name: "닫기", exact: true }) });
    if (await notice.count()) await notice.first().getByRole("button", { name: "닫기", exact: true }).click();
    await capture(page, `07-preview-return-${width}`);
    await noHorizontalScroll(page);
  });
  test(`흰 소셜 버튼과 분리한 선택 약관 ${width}px`, async ({ page, request }) => {
    await mockServer(request).scenario({ consents: "on" });
    await page.setViewportSize({ width, height: 812 });
    await start(page); await page.goto("/mypage#accounts");
    const kakao = page.getByRole("button", { name: "Kakao 계정으로 계속", exact: true });
    await expect(kakao).toHaveCSS("background-color", "rgb(255, 255, 255)");
    const google = page.getByRole("button", { name: "Google 계정으로 계속", exact: true });
    await expect(google).toHaveCSS("border-radius", "24px");
    await page.locator("#consents").scrollIntoViewIfNeeded();
    await expect(page.getByRole("list", { name: "선택 동의 항목" })).toHaveCount(0);
    await capture(page, `04-social-and-terms-${width}`);
    const trigger = page.getByRole("button", { name: "선택 약관 동의", exact: true });
    await trigger.click();
    const dialog = page.getByRole("dialog", { name: "선택 약관 동의", exact: true });
    const close = dialog.getByRole("button", { name: "선택 약관 닫기" });
    await expect(close).toBeFocused();
    await expect(dialog.locator("li[data-doc]")).toHaveCount(3);
    await expect(dialog).toContainText("동의하지 않아도");
    await capture(page, `05-optional-dialog-${width}`);
    await close.focus(); await page.keyboard.press("Shift+Tab");
    expect(await dialog.evaluate((node) => node.contains(document.activeElement))).toBe(true);
    await dialog.locator('[data-doc="location"]').getByRole("button", { name: "동의하기", exact: true }).click();
    await expect(dialog.locator('[data-doc="location"]')).toContainText("동의를 기록했어요");
    await dialog.locator('[data-doc="location"]').getByRole("button", { name: "전문 보기" }).click();
    await expect(dialog.locator('[data-doc="location"] [data-optional-full]')).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(1);
    await dialog.locator('[data-doc="location"]').getByRole("button", { name: "전문 접기", exact: true }).click();
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0); await expect(trigger).toBeFocused();
    await page.getByRole("button", { name: "약관 전문 확인", exact: true }).click();
    await expect(page.getByRole("dialog", { name: "약관 전문", exact: true })).toBeVisible();
    await capture(page, `06-required-terms-${width}`);
    await noHorizontalScroll(page);
  });
}
test("지도 도구는 5초 뒤 접히고 키보드 조작 중에는 유지된다", async ({ page, request }) => {
  await openFinished(page, request); await page.waitForTimeout(400);
  const tools = page.getByRole("group", { name: "지도 단추" });
  await tools.getByRole("button", { name: "지도 단추 펼치기" }).click();
  await page.keyboard.press("Tab");
  await expect(tools.getByRole("button", { name: "확대", exact: true })).toBeFocused();
  await page.mouse.move(0, 0); await page.waitForTimeout(5_300);
  await expect(tools.getByRole("button", { name: "확대", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "목록 높이 바꾸기", exact: true }).focus();
  await expect(tools.getByRole("button", { name: "지도 단추 펼치기" })).toBeVisible({ timeout: 7_000 });
});


test("지도를 움직이는 동안 정보와 단추가 사라졌다가 멈추면 돌아온다", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await openFinished(page, request); await page.waitForTimeout(400);
  const intro = toast(page, "계획 확인 화면이에요");
  await expect(intro).toHaveCount(0);
  const region = page.getByRole("region", { name: "여행 지도", exact: true });
  const box = (await region.boundingBox())!;
  await page.mouse.move(box.x + 150, box.y + 200); await page.mouse.down();
  await page.mouse.move(box.x + 220, box.y + 220, { steps: 10 });
  await expect(region).toHaveAttribute("data-moving", "true");
  await expect(page.locator("[class*=mapChips]")).toHaveAttribute("aria-hidden", "true");
  await expect(page.locator("[data-map-controls]")).toHaveCSS("opacity", "0");
  await page.mouse.up();
  await expect(region).not.toHaveAttribute("data-moving", "true");
  await expect(page.locator("[data-map-controls]")).toHaveCSS("opacity", "1");
  await expect(page.locator("[class*=mapChips]")).not.toHaveAttribute("aria-hidden", "true");
});


test("같은 좌표의 일정 40개도 겹치지 않게 표시하고 목록에는 모두 남긴다", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await openFinished(page, request, (view) => {
    const sample = view.review.items[1];
    view.review.items = Array.from({ length: 40 }, (_, i) => ({ ...sample, id: `dense-${i}`, title: `밀집 일정 ${i+1}`, index: i, place: { ...sample.place, latitude: 37.5796, longitude: 126.977 } }));
    view.review.moves = [];
  });
  await expect(page.locator("[data-pin-body]")).toHaveCount(40);
  await expect.poll(() => separate(page)).toEqual([]);
  expect(await page.locator('[data-pin-group]:not([data-pin-group=""])').count()).toBeGreaterThan(0);
  await expect(page.getByRole("article", { name: /^밀집 일정/ })).toHaveCount(40);
});

test("일정을 펼쳐 스크롤해도 왼쪽 시각은 해당 일정이 끝날 때까지 따라온다", async ({ page, request }) => {
  await openFinished(page, request); await head(page, "경복궁 관람").click();
  const body = page.locator("div[class*=sheetBody]");
  const time = page.getByRole("button", { name: /^경복궁 관람 시간 고치기/ });
  await expect(time).toHaveCSS("position", "sticky");
  await body.evaluate((node) => {
    const entry = node.querySelector('[data-entry-id="0-0"]')!;
    node.scrollTop += entry.getBoundingClientRect().top - node.getBoundingClientRect().top + 30;
  });
  const before = (await time.boundingBox())!;
  await body.evaluate((node) => { node.scrollTop += 25; });
  const after = (await time.boundingBox())!;
  expect(Math.abs(after.y-before.y)).toBeLessThan(2);
  expect(after.y).toBeGreaterThanOrEqual((await body.boundingBox())!.y-1);
});


test("비교 HTML에서 이전안·수정안과 두 화면 크기를 전환할 수 있다", async ({ page }) => {
  test.skip(!output, "촬영 모음을 만들 때 함께 확인합니다");
  await page.goto(pathToFileURL(resolve(output!, "index.html")).href);
  await expect(page.getByRole("heading", { name: "지도·검증·계정 수정안 비교" })).toBeVisible();
  const patterns = await page.locator("img[data-pattern]").evaluateAll((nodes) => nodes.map((node) => (node as HTMLElement).dataset.pattern!));
  for (const pattern of patterns) for (const width of [375,1280]) await access(resolve(output!, pattern.replace("{w}",String(width))));
  await page.getByRole("button", { name: "수정안", exact: true }).click();
  await expect(page.locator("figure.before").first()).toBeHidden();
  await expect(page.locator("figure.after").first()).toBeVisible();
  await page.getByRole("button", { name: "이전안", exact: true }).click();
  await expect(page.locator("figure.after").first()).toBeHidden();
  await page.getByRole("button", { name: "나란히 보기", exact: true }).click();
  await expect(page.locator("figure.before").first()).toBeVisible();
  await page.getByLabel("촬영 화면").selectOption("1280");
  await expect(page.locator("figure.after img").first()).toHaveAttribute("src", /1280\.png$/);
  await page.setViewportSize({ width:375,height:812 }); await noHorizontalScroll(page);
});
