import { expect, test } from "@playwright/test";
import { mockServer, noHorizontalScroll } from "./helpers";
import { card, openFinished } from "./plan-check-kit";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

for (const width of [375, 1280]) {
  test(`${width}px 시험 안내는 공통 토스트로 나오고 자동으로 사라진다`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    await openFinished(page, request, (view) => {
      view.test_scenario = { code: "test1", name: "서울 2일 기본 일정", mode: "prepared_text", catalog_version: "seoul-text-v1", description: "시험" };
    }, { intakeEvents: "off" }, false);
    await expect(page.locator('[data-stage] > p[class*="streamNote"]')).toHaveCount(0);
    const toast = page.getByRole("status").filter({ hasText: "시험 계획 test1" });
    await expect(toast).toBeVisible();
    const toastBox = await toast.boundingBox();
    const screenBox = await page.locator('[data-stage="done"]').boundingBox();
    expect(toastBox!.y).toBeGreaterThanOrEqual(screenBox!.y + 60);
    await noHorizontalScroll(page);
    await page.screenshot({ path: test.info().outputPath(`toast-${width}.png`), animations: "disabled" });
    await expect(toast).toHaveCount(0, { timeout: 6000 });
    await expect(card(page, "경복궁 관람")).toBeVisible();
  });

  test(`${width}px 최상단은 첫 일정 앞에 추가하고 다시 올라오면 복원한다`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    const api = await openFinished(page, request, undefined, { intakeEvents: "off" });
    const body = page.locator('div[class*="sheetBody"]');
    const seam = page.locator("[data-insert-near]");
    await body.evaluate((element) => { element.scrollTop = 0; });
    await expect(seam).toHaveAttribute("data-insert-point", "1:item:0-0");
    await body.evaluate((element) => { element.scrollTop = element.scrollHeight; });
    await expect(seam).toHaveAttribute("data-insert-point", "1:end");
    await body.evaluate((element) => { element.scrollTop = 0; });
    await expect(seam).toHaveAttribute("data-insert-point", "1:item:0-0");
    const add = seam.getByRole("button", { name: "경복궁 관람 전에 일정 추가", exact: true });
    const buttonBox = await add.boundingBox(), firstBox = await card(page, "경복궁 관람").boundingBox();
    expect(buttonBox!.y + buttonBox!.height).toBeLessThanOrEqual(firstBox!.y + 1);
    await page.screenshot({ path: test.info().outputPath(`first-add-${width}.png`), animations: "disabled" });
    await add.click();
    const form = page.getByRole("form", { name: "일정 추가", exact: true });
    await expect(form.getByLabel("시작", { exact: true })).toHaveValue("08:00");
    await page.getByRole("searchbox", { name: "장소 검색", exact: true }).fill("올리브영");
    await page.getByRole("list", { name: "장소 검색 결과" }).getByRole("button", { name: /올리브영 명동 플래그십/ }).click();
    await form.getByLabel("일정 이름", { exact: true }).fill("궁궐 전 잠깐 방문");
    await form.getByRole("button", { name: "일정에 추가", exact: true }).click();
    await expect.poll(async () => (await api.received("POST", "/edits")).length).toBe(1);
    const first = page.locator('li[data-type="item"]').first().getByRole("article");
    await expect(first).toHaveAccessibleName("올리브영 명동 플래그십");
    await expect(first).toHaveAttribute("id", "plan-card-0-3");
    await first.getByRole("heading").getByRole("button").click();
    await expect(first).toContainText("궁궐 전 잠깐 방문");
    await noHorizontalScroll(page);
  });
}
