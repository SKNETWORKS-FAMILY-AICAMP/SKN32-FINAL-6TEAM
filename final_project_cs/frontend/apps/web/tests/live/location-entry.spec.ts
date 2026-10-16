import { expect, test, type Page } from "@playwright/test";
import { galleryShot, mockServer } from "./helpers";
import { openFinished } from "./plan-check-kit";
import { allowLocation, changeLocationConsent, countLocationAsks, locationAsks, startWithLocationConsent } from "./location-kit";

const tools = (page: Page) => page.getByRole("group", { name: "지도 단추" });
const locate = (page: Page) => tools(page).getByRole("button", { name: "내 위치로", exact: true });
const dot = (page: Page) => page.getByRole("img", { name: "내 위치", exact: true });
async function expand(page: Page) { await tools(page).getByRole("button", { name: "지도 단추 펼치기" }).click(); }
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

for (const width of [375, 1280]) test(`${width}px: 동의 전에도 왼쪽 내 위치 버튼·도움말·버튼별 누름 영역을 제공하고 취소 시 위치를 읽지 않는다`, async ({ page, request }) => {
  await page.setViewportSize({ width, height: 900 });
  await countLocationAsks(page);
  await openFinished(page, request);
  const tour = page.getByRole("status").filter({ hasText: "계획 확인 화면이에요" });
  await expect(tour).toHaveCount(0); // Let the unrelated introduction finish before inspecting tools.
  await page.getByRole("button", { name: "목록 높이 바꾸기" }).focus();
  for (let press = 0; press < 5; press += 1) await page.keyboard.press("ArrowUp");
  await expand(page);
  await expect(tools(page)).toHaveAttribute("data-layout", "row");
  const boxes = await tools(page).getByRole("button").evaluateAll(nodes => nodes.map(node => ({ label: node.getAttribute("aria-label"), box: node.getBoundingClientRect().toJSON() })));
  for (const item of boxes) {
    expect(item.box.width, `${item.label} 누름 폭`).toBeGreaterThanOrEqual(44);
    // 거리·접기 버튼은 44×40px, 내 위치를 포함한 원형 도구는 44×44px를 유지한다.
    expect(item.box.height, `${item.label} 누름 높이`).toBeGreaterThanOrEqual(item.label === "지도 단추 접기" ? 40 : 44);
  }
  if (await tools(page).getAttribute("data-layout") === "row") expect(boxes.at(-1)!.box.x).toBeLessThan(boxes.at(-2)!.box.x);
  await tools(page).getByRole("button", { name: "지도 단추 접기" }).focus();
  for (let tab = 0; tab < 4; tab += 1) await page.keyboard.press("Tab");
  await expect(locate(page)).toBeFocused();
  await expect(locate(page).getByRole("tooltip")).toBeVisible();
  const foldBefore = (await tools(page).getByRole("button", { name: "지도 단추 접기" }).boundingBox())!;
  await galleryShot(page, `mockups/location-entry-2026-10-11-v2/tools-${width}.png`);
  await locate(page).click();
  const dialog = page.getByRole("dialog", { name: "내 위치로 이동" });
  await expect(dialog).toBeVisible();
  expect(await locationAsks(page)).toBe(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await galleryShot(page, `mockups/location-entry-2026-10-11-v2/consent-${width}.png`);
  await page.waitForTimeout(5_300); // Reading the consent must not fold away its trigger.
  await dialog.getByRole("button", { name: "그만두기" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(locate(page)).toBeFocused();
  expect(await locationAsks(page)).toBe(0);
  const foldAfter = (await tools(page).getByRole("button", { name: "지도 단추 접기" }).boundingBox())!;
  expect(foldAfter.x).toBeCloseTo(foldBefore.x, 0);
});

test("버튼에서 동의하면 위치 점을 그리고 카메라를 그곳으로 이동하며 동의 철회 뒤에는 지운다", async ({ page, context, request }) => {
  await page.setViewportSize({ width: 375, height: 900 });
  await allowLocation(context, { latitude: 37.5512, longitude: 126.9882 });
  await countLocationAsks(page);
  await openFinished(page, request);
  await expand(page);
  await locate(page).click();
  await page.getByRole("dialog", { name: "내 위치로 이동" }).getByRole("button", { name: /에 동의하고 계속/ }).click();
  await expect(dot(page)).toBeInViewport();
  await expect.poll(async () => {
    const box = (await dot(page).boundingBox())!;
    const map = (await page.getByRole("region", { name: "여행 지도" }).boundingBox())!;
    return Math.abs(box.x + box.width / 2 - map.x - map.width / 2);
  }).toBeLessThan(3);
  expect(await locationAsks(page)).toBeGreaterThan(0);
  await galleryShot(page, "mockups/location-entry-2026-10-11-v2/located-375.png");
  await changeLocationConsent(page, false);
  await expect(dot(page)).toHaveCount(0);
});

test("시간 초과 뒤에도 버튼을 다시 눌러 성공하면 점과 카메라를 복구한다", async ({ page, context, request }) => {
  await allowLocation(context, { latitude: 37.5512, longitude: 126.9882 });
  await startWithLocationConsent(page, true);
  await page.addInitScript(() => {
    const geo = navigator.geolocation;
    const current = geo.getCurrentPosition.bind(geo);
    let tries = 0;
    geo.watchPosition = (_success, error) => { setTimeout(() => error?.({ code: 3, message: "test timeout" } as GeolocationPositionError), 0); return 1; };
    geo.clearWatch = () => {};
    geo.getCurrentPosition = (success, error, options) => { tries += 1; if (tries === 1) setTimeout(() => error?.({ code: 3, message: "test timeout" } as GeolocationPositionError), 0); else current(success, error, options); };
  });
  await openFinished(page, request);
  const error = page.getByRole("alert").filter({ hasText: "내 위치를 아직 찾지 못했어요" });
  await expect(error).toHaveCount(1);
  await error.getByRole("button", { name: "닫기", exact: true }).click();
  await expand(page);
  await locate(page).click();
  await expect(error).toHaveCount(1);
  await error.getByRole("button", { name: "닫기", exact: true }).click();
  await locate(page).click();
  await expect(dot(page)).toBeInViewport();
  await expect(error).toHaveCount(0);
});

for (const reason of ["denied", "unsupported"] as const) test(`${reason}: 실패 후에도 내 위치 버튼과 오류 토스트 하나를 유지한다`, async ({ page, request }) => {
  await startWithLocationConsent(page, true);
  await page.addInitScript((reason) => {
    if (reason === "unsupported") Object.defineProperty(navigator, "geolocation", { configurable: true, value: undefined });
    else {
      navigator.permissions.query = async () => ({ state: "denied" } as PermissionStatus);
      navigator.geolocation.getCurrentPosition = (_success, error) => error?.({ code: 1 } as GeolocationPositionError);
    }
  }, reason);
  await openFinished(page, request);
  const error = page.getByRole("alert").filter({ hasText: reason === "denied" ? "위치 권한이 꺼져" : "이 브라우저는 위치" });
  await expect(error).toHaveCount(1);
  await error.getByRole("button", { name: "닫기", exact: true }).click();
  await expand(page);
  await expect(locate(page)).toBeEnabled();
  await locate(page).click();
  await expect(error).toHaveCount(1);
  await expect(dot(page)).toHaveCount(0);
  await expect(page.locator("[data-my-location-notice]")).toHaveCount(0);
});

test("약관 전문은 동의 창을 대체하고 Esc로 돌아온 뒤 취소하면 초점을 돌려준다", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 900 });
  await openFinished(page, request);
  await expand(page);
  await locate(page).click();
  await page.getByRole("dialog", { name: "내 위치로 이동" }).getByRole("button", { name: "전문 보기" }).click();
  await expect(page.locator("dialog[open]")).toHaveCount(1);
  await expect(page.getByRole("dialog", { name: "내 위치로 이동" })).toHaveCount(0);
  await page.keyboard.press("Escape");
  const prompt = page.getByRole("dialog", { name: "내 위치로 이동" });
  await expect(prompt).toBeVisible();
  for (let tab = 0; tab < 6; tab += 1) { await page.keyboard.press("Tab"); expect(await prompt.evaluate(node => node.contains(document.activeElement))).toBe(true); }
  await page.keyboard.press("Escape");
  await expect(prompt).toHaveCount(0);
  await expect(locate(page)).toBeFocused();
});

test("거절했던 권한을 허용한 뒤 버튼으로 찾으면 이후 위치 이동도 계속 따라간다", async ({ page, context, request }) => {
  await allowLocation(context, { latitude: 37.5512, longitude: 126.9882 });
  await startWithLocationConsent(page, true);
  await page.addInitScript(() => {
    const state = window as Window & { __locationPermissionRestored?: boolean };
    const query = navigator.permissions.query.bind(navigator.permissions);
    navigator.permissions.query = descriptor => descriptor.name === "geolocation" && !state.__locationPermissionRestored ? Promise.resolve({ state: "denied" } as PermissionStatus) : query(descriptor);
  });
  await openFinished(page, request);
  await page.getByRole("alert").filter({ hasText: "위치 권한이 꺼져" }).getByRole("button", { name: "닫기", exact: true }).click();
  await expand(page);
  await page.evaluate(() => { (window as Window & { __locationPermissionRestored?: boolean }).__locationPermissionRestored = true; });
  await locate(page).click();
  await expect(dot(page)).toBeInViewport();
  await page.waitForTimeout(800);
  const old = (await dot(page).boundingBox())!;
  await context.setGeolocation({ latitude: 37.5552, longitude: 126.9882 });
  await expect.poll(async () => old.y - (await dot(page).boundingBox())!.y, { timeout: 10_000 }).toBeGreaterThan(10);
});

test("위치 권한을 확인하는 사이 동의를 철회하면 GPS 조회를 시작하지 않는다", async ({ page, request }) => {
  await startWithLocationConsent(page, true);
  await page.addInitScript(() => {
    const state = window as Window & { __finishLocationPermission?: () => void; __currentLocationCalls?: number };
    let permissions = 0;
    navigator.permissions.query = async () => {
      permissions += 1;
      if (permissions === 1) return { state: "granted" } as PermissionStatus;
      return new Promise<PermissionStatus>(resolve => { state.__finishLocationPermission = () => resolve({ state: "granted" } as PermissionStatus); });
    };
    navigator.geolocation.watchPosition = (_success, error) => { setTimeout(() => error?.({ code: 3 } as GeolocationPositionError), 0); return 1; };
    navigator.geolocation.clearWatch = () => {};
    navigator.geolocation.getCurrentPosition = () => { state.__currentLocationCalls = (state.__currentLocationCalls ?? 0) + 1; };
  });
  await openFinished(page, request);
  await page.getByRole("alert").filter({ hasText: "내 위치를 아직 찾지 못했어요" }).getByRole("button", { name: "닫기", exact: true }).click();
  await expand(page);
  await locate(page).click();
  await expect.poll(() => page.evaluate(() => Boolean((window as Window & { __finishLocationPermission?: () => void }).__finishLocationPermission))).toBe(true);
  await changeLocationConsent(page, false);
  await page.evaluate(() => { (window as Window & { __finishLocationPermission?: () => void }).__finishLocationPermission?.(); });
  await page.waitForTimeout(250);
  expect(await page.evaluate(() => (window as Window & { __currentLocationCalls?: number }).__currentLocationCalls ?? 0)).toBe(0);
  await expect(dot(page)).toHaveCount(0);
});
