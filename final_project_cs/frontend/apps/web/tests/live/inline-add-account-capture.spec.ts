import { expect, test, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { mockServer } from "./helpers";
import { head, openFinished } from "./plan-check-kit";
import { useMapTiles } from "./capture-map-tiles";

const output = process.env.INLINE_ACCOUNT_SHOTS;
test.skip(!output, "새 촬영 경로를 지정할 때만 실행합니다");

async function centre(page: Page, key: string) {
  await page.locator("div[class*=sheetBody]").evaluate((body, key) => {
    const point = body.querySelector<HTMLElement>(`[data-insert-point="${key}"]`)!;
    const area = body.getBoundingClientRect();
    body.scrollTop += point.getBoundingClientRect().top - (area.top + area.height / 2);
  }, key);
  await expect(page.locator("[data-insert-near]")).toHaveAttribute("data-insert-point", key);
}

for (const width of [375, 1280]) {
  test(`일정 사이 추가·계정·약관 실제 화면 촬영 ${width}px`, async ({ page, request }) => {
    test.setTimeout(100_000);
    await mkdir(output!, { recursive: true });
    await mockServer(request).reset();
    await page.setViewportSize({ width, height: 812 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    const ready = await useMapTiles(page);
    await openFinished(page, request, undefined, { intakeEvents: "off", intakeRoutes: "on" });
    const capture = async (name: string) => {
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.mouse.move(0, 0);
      await page.screenshot({ path: `${output}/${name}-${width}.png`, fullPage: true });
    };
    await ready();
    await capture("01-after-travel-plus");
    await head(page, "경복궁 관람").click();
    await centre(page, "1:move:0-0:0-1");
    await capture("02-before-travel-plus");
    await page.locator("[data-insert-near] > button").click();
    const form = page.getByRole("form", { name: "일정 추가", exact: true });
    // Use the product's existing height control, then show the search within the list.
    for (let i = 0; i < 4; i++) await page.getByRole("button", { name: "목록 높이 바꾸기", exact: true }).press("ArrowUp");
    await expect(form.getByLabel("일정 이름", { exact: true })).toHaveAccessibleName("일정 이름");
    await form.getByLabel("일정 이름", { exact: true }).fill("명동 매장 둘러보기");
    await form.getByLabel("장소 검색", { exact: true }).fill("올리브영");
    const result = form.getByRole("list", { name: "장소 검색 결과" }).getByRole("button", { name: /올리브영 명동 플래그십/ });
    await expect(result).toBeVisible();
    await result.scrollIntoViewIfNeeded();
    await capture("03-place-results");
    await result.click();
    await form.getByRole("button", { name: "다시 검색", exact: true }).scrollIntoViewIfNeeded();
    await capture("04-place-selected");
    await mockServer(request).scenario({ consents: "on" });
    await page.goto("/mypage#accounts");
    const group = page.getByRole("group", { name: "소셜 계정" });
    await expect(group.getByRole("button", { name: "Kakao 계정으로 계속", exact: true })).toBeVisible();
    await group.scrollIntoViewIfNeeded();
    await capture("05-social-accounts");
    await page.locator("#consents").scrollIntoViewIfNeeded();
    await capture("06-optional-consents");
    await page.getByRole("button", { name: "약관 전문 확인", exact: true }).click();
    await expect(page.getByRole("dialog", { name: "약관 전문", exact: true })).toBeVisible();
    await capture("07-required-terms");
  });
}
