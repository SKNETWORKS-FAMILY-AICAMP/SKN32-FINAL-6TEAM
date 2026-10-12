import { expect, test, type Page } from "@playwright/test";
import { mockServer } from "./helpers";
import { INTAKE, head, openFinished } from "./plan-check-kit";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

async function centre(page: Page, key: string) {
  await page.locator("div[class*=sheetBody]").evaluate((body, key) => {
    const point = body.querySelector<HTMLElement>(`[data-insert-point="${key}"]`)!;
    const area = body.getBoundingClientRect();
    body.scrollTop += point.getBoundingClientRect().top - (area.top + area.height / 2);
  }, key);
  await expect(page.locator("[data-insert-near]")).toHaveAttribute("data-insert-point", key);
}

for (const width of [375, 1280]) {
  test(`${width}px: 스크롤한 일정 사이에서 장소를 검색하고 정확한 지점으로 추가한다`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    const api = await openFinished(page, request, undefined, { intakeEvents: "off" });
    await expect(page.locator("[data-insert-near]")).toHaveCount(1);
    // Expand the first stop so both seams can actually reach the viewport centre.
    await head(page, "경복궁 관람").click();
    await centre(page, "1:move:0-0:0-1");
    const beforeTravel = page.getByRole("button", { name: "경복궁 관람 다음 이동 전에 일정 추가", exact: true });
    await expect(beforeTravel).toHaveAccessibleName("경복궁 관람 다음 이동 전에 일정 추가");
    await beforeTravel.click();
    let form = page.getByRole("form", { name: "일정 추가", exact: true });
    await page.getByRole("button", { name: "일정 추가 취소", exact: true }).click();
    await expect(beforeTravel).toBeFocused();
    await expect(beforeTravel).toBeInViewport();
    await centre(page, "1:item:0-1");
    await page.locator("[data-insert-near] > button").click();
    form = page.getByRole("form", { name: "일정 추가", exact: true });
    await page.getByLabel("장소 검색", { exact: true }).fill("올리브영");
    await page.getByRole("list", { name: "장소 검색 결과" }).getByRole("button", { name: /올리브영 명동 플래그십/ }).click();
    await expect(form.getByLabel("시작", { exact: true })).toHaveValue("10:39");
    await expect(form.getByLabel("날짜", { exact: true })).toHaveValue("2026-10-01");
    await form.getByLabel("일정 이름", { exact: true }).fill("명동 매장 둘러보기");
    await expect(page.getByRole("button", { name: "다시 검색", exact: true })).toBeVisible();
    await form.getByRole("button", { name: "일정에 추가", exact: true }).click();
    await expect(form).toHaveCount(0);
    const posted = await api.received("POST", "/edits");
    expect(posted).toHaveLength(1);
    const edits = posted[0].body!.edits as { field: string; value: unknown }[];
    expect(edits.find((edit) => edit.field === "items[3].place")?.value).toMatchObject({ name: "올리브영 명동 플래그십", latitude: 37.5637, longitude: 126.9851, source: "kakao" });
    expect(edits.find((edit) => edit.field === "items[3].starts_at")?.value).toBe("10:39");
    expect(await page.locator('li[data-type="item"]').evaluateAll((rows) => rows.map((row) => row.getAttribute("data-entry-id")))).toEqual(["0-0", "0-3", "0-1", "0-2"]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}

test("키보드로 다른 추가 위치를 고르고 취소하면 그 +로 초점이 돌아온다", async ({ page, request }) => {
  const api = await openFinished(page, request, undefined, { intakeEvents: "off" });
  const first = page.getByRole("button", { name: "경복궁 관람 전에 일정 추가", exact: true });
  await first.focus();
  await page.keyboard.press("Tab");
  await page.keyboard.press("Shift+Tab");
  await expect(first).toBeFocused();
  await expect(first.getByRole("tooltip")).toBeVisible();
  await first.press("Enter");
  await expect(page.getByLabel("장소 검색", { exact: true })).toBeFocused();
  await page.getByRole("button", { name: "일정 추가 취소", exact: true }).click();
  await expect(first).toBeFocused();
  expect(await api.received("POST", "/edits")).toHaveLength(0);
});

test("추가 저장을 거절하면 검색 선택과 입력을 보존해 수정 후 재시도할 수 있다", async ({ page, request }) => {
  const api = await openFinished(page, request, undefined, { intakeEvents: "off" });
  await page.locator("[data-insert-near] > button").click();
  const form = page.getByRole("form", { name: "일정 추가", exact: true });
  await page.getByLabel("장소 검색", { exact: true }).fill("올리브영");
  await page.getByRole("list", { name: "장소 검색 결과" }).getByRole("button", { name: /올리브영 명동 플래그십/ }).click();
  await form.getByLabel("일정 이름", { exact: true }).fill("명동 쇼핑");
  const route = `**/v1/web/trip-intakes/${INTAKE}/edits`;
  await page.route(route, (request) => request.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ error: { code: "schedule_conflict", message: "앞뒤 일정과 겹쳐요. 시간을 조정해 주세요." } }) }));
  await form.getByRole("button", { name: "일정에 추가", exact: true }).click();
  await expect(form.getByRole("alert")).toContainText("앞뒤 일정과 겹쳐요");
  await expect(form.getByLabel("일정 이름", { exact: true })).toHaveValue("명동 쇼핑");
  await expect(page.getByRole("button", { name: "다시 검색", exact: true })).toBeVisible();
  expect(await api.received("POST", "/edits")).toHaveLength(0);
  await page.unroute(route);
  await form.getByLabel("시작", { exact: true }).fill("14:00");
  await form.getByLabel("끝", { exact: true }).fill("15:00");
  await form.getByRole("button", { name: "일정에 추가", exact: true }).click();
  await expect(form).toHaveCount(0);
  expect(await api.received("POST", "/edits")).toHaveLength(1);
});
