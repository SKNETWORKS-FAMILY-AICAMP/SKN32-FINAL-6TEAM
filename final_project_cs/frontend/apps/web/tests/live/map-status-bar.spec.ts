import { expect, test, type Page } from "@playwright/test";
import { mockServer } from "./helpers";
import { changedBadge, mapSettled, needsBadge, openFinished, pin, type Json } from "./plan-check-kit";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });
const shot = async (page: Page, name: string) => {
  if (process.env.MAP_STATUS_SHOTS) await page.screenshot({ path: `${process.env.MAP_STATUS_SHOTS}/${name}.png`, fullPage: true });
};

test("확인·변경·위치 표시가 하나의 막대에 나란히 붙고 시간 초기화는 변경 메뉴에서 동작한다", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  const addHotel = (view: Json) => {
    view.review.items.push({ ...view.review.items[2], id: "0-3", index: 3, title: "호텔", starts_at: "21:00", ends_at: "22:00", status: "review", place: null, place_state: "missing",
      rows: [{ row: "place", result: "warn", text: "호텔 위치를 골라 주세요" }] });
  };
  await page.route("**/v1/web/trip-intakes/**/edits", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    addHotel(body);
    await route.fulfill({ response, json: body });
  });
  // All responses use the four-stop fixture; the mock server's default SSE stream has only three stops.
  const server = await openFinished(page, request, addHotel, { intakeRoutes: "on", intakeEvents: "off" });
  await page.getByRole("button", { name: /^광장시장 시간 고치기/ }).click();
  const form = page.getByRole("form", { name: "광장시장 시간 고치기" });
  await form.getByLabel("시작", { exact: true }).fill("11:30");
  await form.getByRole("button", { name: "적용" }).click();
  await expect(changedBadge(page)).toHaveText("변경3");
  await page.getByRole("status").filter({ hasText: /시간을 바꿨어요/ }).getByRole("button", { name: "닫기", exact: true }).click();
  const group = page.getByRole("group", { name: "일정 확인과 변경" });
  await expect(group.getByText("위치 미정 · 호텔", { exact: true })).toBeVisible();
  const [need, change, location, bar] = await Promise.all([needsBadge(page).boundingBox(), changedBadge(page).boundingBox(), group.getByText("위치 미정 · 호텔", { exact: true }).boundingBox(), group.boundingBox()]);
  expect(change!.x - need!.x - need!.width).toBeLessThanOrEqual(2);
  expect(location!.x).toBeGreaterThan(change!.x + change!.width - 2);
  expect(Math.abs(need!.y + need!.height / 2 - location!.y - location!.height / 2)).toBeLessThan(2);
  expect(bar!.x + bar!.width).toBeLessThanOrEqual(375);
  await expect(page.locator("header[class*=sheetHead]").getByRole("button", { name: /^바뀐 일정|^시간 조정/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^시간 조정/ })).toHaveCount(0);
  await shot(page, "01-status-bar");
  await changedBadge(page).click();
  const reset = page.getByRole("button", { name: /^시간 조정.*모두 처음으로/ });
  await expect(reset).toBeVisible();
  await expect(reset).toHaveAttribute("aria-label", "시간 조정 3곳 모두 처음으로");
  expect((await reset.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  const panel = await page.getByRole("region", { name: "변경 관리" }).boundingBox();
  expect(panel!.x).toBeGreaterThanOrEqual(0);
  expect(panel!.x + panel!.width).toBeLessThanOrEqual(375);
  await shot(page, "02-time-reset-menu");
  const before = (await server.received("POST", "/edits")).length;
  await reset.click();
  await expect.poll(async () => (await server.received("POST", "/edits")).length).toBe(before + 1);
  await expect(changedBadge(page)).toHaveCount(0);
  await expect(needsBadge(page)).toBeFocused();
  await page.setViewportSize({ width: 1280, height: 720 });
  await shot(page, "03-desktop-status");
});

test("변경 메뉴는 키보드로 열고 이동하며 Escape를 누르면 변경 버튼으로 초점이 돌아온다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await page.getByRole("button", { name: /^광장시장 시간 고치기/ }).click();
  const form = page.getByRole("form", { name: "광장시장 시간 고치기" });
  await form.getByLabel("시작", { exact: true }).fill("11:30");
  await form.getByRole("button", { name: "적용" }).click();
  await expect(page.getByRole("status").filter({ hasText: "3개 일정의 시간을 바꿨어요" })).toBeVisible();
  await expect(changedBadge(page)).toHaveText("변경3");
  await changedBadge(page).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: /^시간 조정.*모두 처음으로/ })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: /^시간 조정.*모두 처음으로/ })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("region", { name: "변경 관리" })).toHaveCount(0);
  await expect(changedBadge(page)).toBeFocused();
  await page.keyboard.press("Space");
  await expect(page.getByRole("button", { name: /^시간 조정.*모두 처음으로/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /^시간 조정.*모두 처음으로/ })).toHaveAttribute("aria-label", "시간 조정 3곳 모두 처음으로");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: /^시간 조정.*모두 처음으로/ })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect.poll(async () => (await server.received("POST", "/edits")).length).toBe(2);
  const resetRequest = (await server.received("POST", "/edits"))[1].body as Json;
  expect(resetRequest.edits.map((edit: Json) => [edit.field, edit.value])).toEqual([
    ["items[0].starts_at", "09:00"], ["items[0].ends_at", "10:30"],
    ["items[1].starts_at", "11:00"], ["items[1].ends_at", "12:00"],
    ["items[2].starts_at", "12:30"], ["items[2].ends_at", "13:30"],
  ]);
  await expect(changedBadge(page)).toHaveCount(0);
  await expect(needsBadge(page)).toBeFocused();
});

test("확대한 경로선에 수단 이름이 붙고 지도 이동·축소에 따라 바뀌며 클릭은 선으로 통과한다", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await openFinished(page, request, undefined, { intakeRoutes: "on" });
  // Centre on an actual route end before zooming, rather than magnifying an empty area between routes.
  await pin(page, "2.").locator("[data-pin-body]").click();
  await mapSettled(page);
  const map = page.getByRole("region", { name: "여행 지도", exact: true });
  const labels = page.locator("[data-route-label]");
  await expect(page.locator("[data-route-tags]")).toHaveCount(0);
  for (let at = 0; at < 5 && !(await labels.count()); at++) {
    await map.hover({ position: { x: 150, y: 110 } });
    await page.getByRole("group", { name: "지도 단추" }).getByRole("button", { name: "확대", exact: true }).click();
    await page.waitForTimeout(450);
  }
  await expect(labels.first()).toBeVisible();
  await expect(labels.first()).toContainText(/지하철|도보/);
  expect(await labels.first().evaluate((element) => getComputedStyle(element).pointerEvents)).toBe("none");
  const position = (await labels.first().boundingBox())!;
  await shot(page, "04-route-name-on-line");
  await page.mouse.click(position.x + position.width / 2, position.y + position.height / 2);
  const note = page.getByRole("status").filter({ hasText: /^→/ });
  await expect(note).toBeVisible();
  await note.getByRole("button", { name: "닫기", exact: true }).click();
  await page.mouse.move(150, 140);
  await page.mouse.down();
  await page.mouse.move(210, 180, { steps: 8 });
  await page.mouse.up();
  await page.waitForTimeout(500);
  const moved = await labels.first().boundingBox();
  expect(!moved || Math.abs(moved.x - position.x) + Math.abs(moved.y - position.y) > 10).toBe(true);
  for (let at = 0; at < 5; at++) {
    await map.hover({ position: { x: 150, y: 110 } });
    await page.getByRole("group", { name: "지도 단추" }).getByRole("button", { name: "축소", exact: true }).click();
    await page.waitForTimeout(350);
  }
  await expect(labels).toHaveCount(0);
});

test("마커 선택은 일정만 열고 설명 알림을 띄우지 않는다", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await openFinished(page, request);
  await pin(page, "2.").locator("[data-pin-body]").click();
  await expect(page.getByRole("article", { name: "올리브영", exact: true }).getByRole("heading").getByRole("button")).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByRole("status").filter({ hasText: /^2올리브영/ })).toHaveCount(0);
  await shot(page, "05-marker-without-notice");
});
