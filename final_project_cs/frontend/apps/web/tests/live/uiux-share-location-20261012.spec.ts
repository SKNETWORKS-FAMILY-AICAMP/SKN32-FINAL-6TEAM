import { expect, test, type Page } from "@playwright/test";
import { mockServer, openTitle, start, TRIP_ID, tripScreen } from "./helpers";
import { changeLocationConsent, startWithLocationConsent } from "./location-kit";

/** UI·UX 감사에서 찾은 공유창 초점과 GPS 대기 취소의 mock 서버 회귀 시험. */
async function openShare(page: Page) {
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(tripScreen(page)).toBeVisible();
  const menu = await openTitle(page);
  await menu.getByRole("button", { name: "공유하기" }).click();
  return page.getByRole("dialog", { name: "여행계획서 공유" });
}

for (const width of [375, 1280]) test(`공유창 Tab 순환·배경 비활성화·Esc 초점 복귀 (${width}px)`, async ({ page, request }) => {
  await page.setViewportSize({ width, height: 850 });
  await mockServer(request).reset();
  await start(page);
  const sheet = await openShare(page);
  await expect(sheet.getByRole("heading")).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(sheet.getByRole("link", { name: /파일로 내려받기/ })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(sheet.getByRole("button", { name: "닫기", exact: true })).toBeFocused();
  for (let at = 0; at < 12; at += 1) {
    await page.keyboard.press("Tab");
    expect(await sheet.evaluate(element => element.contains(document.activeElement))).toBe(true);
  }
  const menuButton = page.getByRole("button", { name: "메뉴", exact: true, includeHidden: true });
  expect(await menuButton.evaluate(element => Boolean(element.closest("[inert]")))).toBe(true);
  await page.keyboard.press("Escape");
  await expect(sheet).toHaveCount(0);
  await expect(page.locator("#trip-title-share")).toBeFocused();
  expect(await menuButton.evaluate(element => Boolean(element.closest("[inert]")))).toBe(false);
  await menuButton.click();
  await expect(page.getByRole("dialog", { name: "메뉴", exact: true })).toBeVisible();
});

for (const failure of ["missing", "refused"] as const) test(`클립보드 ${failure}에서도 복사 실패를 알리고 공유창을 유지한다`, async ({ page, request }) => {
  await mockServer(request).reset();
  await start(page);
  const sheet = await openShare(page);
  await page.evaluate(value => {
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: value === "missing" ? undefined : { writeText: () => Promise.reject(new DOMException("Denied", "NotAllowedError")) } });
  }, failure);
  await sheet.getByRole("button", { name: "링크 복사" }).click();
  await expect(page.getByRole("status").filter({ hasText: "링크를 복사하지 못했어요" })).toBeVisible();
  await expect(sheet).toBeVisible();
});

interface DelayedLocationWindow extends Window {
  __locationRequested?: boolean;
  __finishLocation?: () => void;
}

async function openDelayedLocation(page: Page) {
  await startWithLocationConsent(page, true);
  await page.addInitScript(() => {
    const state = window as DelayedLocationWindow;
    const query = navigator.permissions.query.bind(navigator.permissions);
    navigator.permissions.query = descriptor => descriptor.name === "geolocation" ? Promise.resolve({ state: "granted" } as PermissionStatus) : query(descriptor);
    navigator.geolocation.watchPosition = () => 1;
    navigator.geolocation.clearWatch = () => {};
    navigator.geolocation.getCurrentPosition = success => {
      state.__locationRequested = true;
      state.__finishLocation = () => success({ coords: { latitude: 37.57, longitude: 126.98, accuracy: 20, altitude: null, altitudeAccuracy: null, heading: null, speed: null }, timestamp: Date.now() } as GeolocationPosition);
    };
  });
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(tripScreen(page)).toBeVisible();
  await page.getByRole("tab", { name: "채팅", exact: true }).click();
  await page.getByRole("textbox", { name: "여행 메시지" }).fill("여기서 경복궁 어떻게 가?");
  await page.getByRole("button", { name: "메시지 전송", exact: true }).click();
  const locate = page.getByRole("button", { name: "내 위치 알려 주고 다시 묻기", exact: true });
  await expect(locate).toBeVisible();
  await locate.click();
  await page.waitForFunction(() => (window as DelayedLocationWindow).__locationRequested);
}

async function finishLocation(page: Page) {
  await page.evaluate(async () => {
    const finish = (window as DelayedLocationWindow).__finishLocation;
    if (!finish) throw new Error("지연 위치 요청이 준비되지 않았습니다");
    finish();
    // GPS 콜백과 React Query 후속 처리가 모두 지나간 뒤 전송 여부를 확인한다.
    await new Promise(resolve => setTimeout(resolve, 150));
  });
}

test("GPS 대기 중 위치 동의를 철회하면 질문과 위치를 전송하지 않는다", async ({ page, request }) => {
  const mock = mockServer(request);
  await mock.reset();
  await openDelayedLocation(page);
  await changeLocationConsent(page, false);
  await expect(page.getByRole("button", { name: "내 위치 알려 주고 다시 묻기", exact: true })).toBeEnabled();
  await finishLocation(page);
  expect(await mock.received("POST", `/trips/${TRIP_ID}/messages`)).toHaveLength(1);
});

test("GPS 대기 중 철회 후 다시 동의해도 취소된 요청은 보내지 않고 새 클릭은 보낸다", async ({ page, request }) => {
  const mock = mockServer(request);
  await mock.reset();
  await openDelayedLocation(page);
  await changeLocationConsent(page, false);
  await expect(page.getByRole("button", { name: "내 위치 알려 주고 다시 묻기", exact: true })).toBeEnabled();
  await changeLocationConsent(page, true);
  await finishLocation(page);
  expect(await mock.received("POST", `/trips/${TRIP_ID}/messages`)).toHaveLength(1);
  await page.getByRole("button", { name: "내 위치 알려 주고 다시 묻기", exact: true }).click();
  await expect.poll(async () => (await mock.received("POST", `/trips/${TRIP_ID}/messages`)).length).toBe(2);
  expect((await mock.received("POST", `/trips/${TRIP_ID}/messages`))[1].body).toHaveProperty("location");
});

test("GPS 대기 중 여행 화면을 나가면 늦게 도착한 위치로 질문을 보내지 않는다", async ({ page, request }) => {
  const mock = mockServer(request);
  await mock.reset();
  await openDelayedLocation(page);
  await page.getByRole("link", { name: "triPilot — 소개 화면으로 돌아가기", exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await finishLocation(page);
  expect(await mock.received("POST", `/trips/${TRIP_ID}/messages`)).toHaveLength(1);
});

test("위치 동의가 유지된 요청은 GPS 응답 뒤 질문과 위치를 한 번 전송한다", async ({ page, request }) => {
  const mock = mockServer(request);
  await mock.reset();
  await openDelayedLocation(page);
  await finishLocation(page);
  await expect.poll(async () => (await mock.received("POST", `/trips/${TRIP_ID}/messages`)).length).toBe(2);
  expect((await mock.received("POST", `/trips/${TRIP_ID}/messages`))[1].body).toHaveProperty("location");
});
