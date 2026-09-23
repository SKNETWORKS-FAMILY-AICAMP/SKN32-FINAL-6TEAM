import { expect, test, type Page } from "@playwright/test";
import { readMapSdk, stubMapSdk, type TestMapProvider } from "./helpers/map-sdk";

const configuredProvider = process.env.MAP_TEST_PROVIDER;
const provider: TestMapProvider = configuredProvider === "google" ? "google" : "naver";
const literalTitle = '<img src=x onerror="window.__mapXss=1">';
const source = [
  "1일차 · 2026-09-15",
  "09:00 첫 지도 장소 · [좌표: 37.58, 126.98]",
  "10:00 좌표가 없는 중간 일정",
  `12:00 ${literalTitle} · [좌표: 37.57, 127.01]`,
  "2일차 · 2026-09-16",
  "09:00 다음 날 첫 장소 · [좌표: 37.52, 126.97]",
  "10:00 다음 날 둘째 장소 · [좌표: 37.51, 127.02]",
  "3일차 · 2026-09-17",
  "09:00 좌표를 확인해야 하는 장소",
].join("\n");

async function registerMapTrip(page: Page) {
  await page.goto("/trips/new");
  await page.getByLabel("여행 계획 필수").fill(source);
  await page.getByRole("button", { name: "검증 하기" }).click();
  await page.getByRole("link", { name: "결과 확인" }).click();
  await page.getByLabel("전체 검증 결과와 일정 조정·안내 범위를 확인했어요.").check();
  await page.getByRole("button", { name: "여행 관리 시작", exact: true }).click();
  await expect(page).toHaveURL(/\/trips\/[^/]+$/);
  await expect(page.getByRole("heading", { name: "첫 지도 장소부터 시작하는 여행", exact: true })).toBeVisible();
}

function marker(page: Page, name: string) {
  return page.getByRole("region", { name: "여행 지도", exact: true }).getByRole("button", { name, exact: true });
}

test.describe(`${provider} 지도 어댑터 · SDK 계약 대역`, () => {
  test.skip(configuredProvider !== "naver" && configuredProvider !== "google", "MAP_TEST_PROVIDER와 같은 공급자로 프로덕션 빌드한 후 실행합니다.");

  test("실제 좌표·원래 방문 번호를 전달하고 선택·일차 변경·좌표 누락·새로고침을 처리한다", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    const sdk = await stubMapSdk(page, provider, { holdFirst: true });
    await registerMapTrip(page);
    await expect(page.locator("#trip-pane-map").getByRole("status")).toBeVisible();
    sdk.releaseFirst();
    const region = page.getByRole("region", { name: "여행 지도", exact: true });
    const firstMarker = marker(page, "1. 첫 지도 장소 · 2026-09-15 09:00");
    const thirdMarker = marker(page, `3. ${literalTitle} · 2026-09-15 12:00`);
    await expect(firstMarker).toBeVisible();
    await expect(thirdMarker).toBeVisible();
    await expect(region.locator("[data-sdk-marker]")).toHaveCount(2);
    await expect(region.locator("img")).toHaveCount(0);
    expect(await page.evaluate(() => window.__mapXss)).toBeUndefined();
    await expect.poll(async () => (await readMapSdk(page))?.markers.filter((item) => item.attached).map((item) => item.position)).toEqual([
      { lat: 37.58, lng: 126.98 },
      { lat: 37.57, lng: 127.01 },
    ]);
    expect(sdk.requests.length).toBeGreaterThan(0);
    expect(sdk.requests.every((request) => request.provider === provider)).toBe(true);
    expect(sdk.requests[0].url).toContain(provider === "naver" ? "test-naver-key" : "test-google-key");

    const timeline = page.locator("#trip-pane-schedule");
    await timeline.getByRole("button", { name: new RegExp(literalTitle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) }).click();
    await expect(thirdMarker).toHaveAttribute("aria-pressed", "true");
    await expect.poll(async () => (await readMapSdk(page))?.pans.at(-1)).toEqual({ lat: 37.57, lng: 127.01 });
    await firstMarker.click();
    await expect(timeline.locator('article[data-selected="true"]')).toContainText("첫 지도 장소");
    await expect(firstMarker).toHaveAttribute("aria-pressed", "true");
    const previousPan = (await readMapSdk(page))?.pans.at(-1);
    await timeline.getByRole("button", { name: /좌표가 없는 중간 일정/ }).click();
    await expect(firstMarker).toHaveAttribute("aria-pressed", "false");
    await expect(thirdMarker).toHaveAttribute("aria-pressed", "false");
    expect((await readMapSdk(page))?.pans.at(-1)).toEqual(previousPan);
    await firstMarker.focus();
    await firstMarker.press("Enter");
    await expect(firstMarker).toHaveAttribute("aria-pressed", "true");
    await expect(timeline.locator('article[data-selected="true"]')).toContainText("첫 지도 장소");

    await page.getByRole("tab", { name: /2일차/ }).click();
    await expect(marker(page, "1. 다음 날 첫 장소 · 2026-09-16 09:00")).toBeVisible();
    await expect(marker(page, "2. 다음 날 둘째 장소 · 2026-09-16 10:00")).toBeVisible();
    await expect(firstMarker).toHaveCount(0);
    await expect.poll(async () => (await readMapSdk(page))?.markers.filter((item) => item.attached).map((item) => item.position)).toEqual([
      { lat: 37.52, lng: 126.97 },
      { lat: 37.51, lng: 127.02 },
    ]);
    await expect.poll(async () => (await readMapSdk(page))?.fits.at(-1)).toEqual([
      { lat: 37.52, lng: 126.97 },
      { lat: 37.51, lng: 127.02 },
    ]);

    await page.getByRole("tab", { name: /3일차/ }).click();
    await expect(page.getByText("표시할 장소 좌표가 없어요.", { exact: true })).toBeVisible();
    await expect(region.locator("[data-sdk-marker]")).toHaveCount(0);
    await page.getByRole("tab", { name: /1일차/ }).click();
    await expect(firstMarker).toBeVisible();
    await page.reload();
    await expect(firstMarker).toBeVisible();
    await expect(thirdMarker).toBeVisible();
    expect(sdk.requests.every((request) => request.provider === provider)).toBe(true);
  });

  test("SDK 로드 실패를 알리고 재시도하면 같은 여행 지도를 복구한다", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    const sdk = await stubMapSdk(page, provider, { failFirst: true });
    await registerMapTrip(page);
    const tripUrl = page.url();
    const mapPane = page.locator("#trip-pane-map");
    await expect(mapPane.getByRole("alert")).toBeVisible();
    await expect(marker(page, "1. 첫 지도 장소 · 2026-09-15 09:00")).toHaveCount(0);
    expect(sdk.selectedRequestCount()).toBe(1);
    await page.getByRole("button", { name: "지도 다시 불러오기", exact: true }).click();
    await expect(marker(page, "1. 첫 지도 장소 · 2026-09-15 09:00")).toBeVisible();
    await expect(mapPane.getByRole("alert")).toHaveCount(0);
    await expect(page).toHaveURL(tripUrl);
    expect(sdk.selectedRequestCount()).toBe(2);
    expect(sdk.requests.every((request) => request.provider === provider)).toBe(true);
  });

  test("모바일에서 숨겨진 지도를 열 때 크기를 다시 계산하고 핀에서 일정 상세로 이동한다", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    const sdk = await stubMapSdk(page, provider);
    await registerMapTrip(page);
    await expect(page.locator("#trip-pane-map")).not.toBeVisible();
    await page.getByRole("tab", { name: "지도", exact: true }).click();
    const firstMarker = marker(page, "1. 첫 지도 장소 · 2026-09-15 09:00");
    await expect(firstMarker).toBeVisible();
    const initialResizes = (await readMapSdk(page))?.resizes ?? 0;
    await page.getByRole("tab", { name: "일정", exact: true }).click();
    await page.setViewportSize({ width: 320, height: 812 });
    await page.getByRole("tab", { name: "지도", exact: true }).click();
    await expect(firstMarker).toBeVisible();
    await expect.poll(async () => (await readMapSdk(page))?.resizes ?? 0).toBeGreaterThan(initialResizes);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await marker(page, `3. ${literalTitle} · 2026-09-15 12:00`).click();
    await page.locator("#trip-pane-map").getByRole("button", { name: "일정 상세 보기", exact: true }).click();
    await expect(page.getByRole("tab", { name: "일정", exact: true })).toHaveAttribute("aria-selected", "true");
    await expect(page.locator('#trip-pane-schedule article[data-selected="true"]')).toContainText(literalTitle);
    await expect(page.locator("#trip-pane-schedule").getByRole("heading", { name: "장소 상세", exact: true })).toBeInViewport();
    expect(sdk.requests.every((request) => request.provider === provider)).toBe(true);
  });
});
