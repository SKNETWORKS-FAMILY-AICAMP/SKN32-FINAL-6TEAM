import { expect, test, type Page } from "@playwright/test";
import { mockServer, noHorizontalScroll, start, TRIP_ID } from "./helpers";
import { allowLocation, startWithLocationConsent } from "./location-kit";
import { readMapSdk, stubMapSdk, type TestMapProvider } from "./map-sdk";

const configuredProvider = process.env.MAP_TEST_PROVIDER;
const provider: TestMapProvider = configuredProvider === "google" ? "google" : "naver";
const literalTitle = '<img src=x onerror="window.__mapXss=1">';
/** The mock server's three-day trip (`tripItems: "map"`): day 1 has a stop without coordinates and one whose title is HTML, day 3 has no coordinates at all. */
async function openMapTrip(page: Page, request: Parameters<typeof mockServer>[0]) {
  await mockServer(request).scenario({ tripItems: "map" });
  await start(page);
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(page.getByRole("heading", { name: "나의 여행", exact: true })).toBeVisible();
}

/** The travel views show one pane at a time; switch with the bottom tabs. */
async function showPane(page: Page, label: "일정" | "지도") {
  await page.getByRole("button", { name: label, exact: true }).click();
}

function marker(page: Page, name: string) {
  return page.getByRole("region", { name: "여행 지도", exact: true }).getByRole("button", { name, exact: true });
}

test.describe(`${provider} 지도 어댑터 · SDK 계약 대역`, () => {
  test.skip(configuredProvider !== "naver" && configuredProvider !== "google", "MAP_TEST_PROVIDER와 같은 공급자로 프로덕션 빌드한 후 실행합니다.");
  test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

  test("실제 좌표·원래 방문 번호를 전달하고 선택·일차 변경·좌표 누락·새로고침을 처리한다", async ({ page, request }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    const sdk = await stubMapSdk(page, provider, { holdFirst: true });
    await openMapTrip(page, request);
    await showPane(page, "지도");
    await expect(page.locator("#trip-pane-map").getByRole("status")).toBeVisible();
    sdk.releaseFirst();
    const region = page.getByRole("region", { name: "여행 지도", exact: true });
    const firstMarker = marker(page, "1. 첫 지도 장소 · 2026-10-01 09:00–10:00");
    const thirdMarker = marker(page, `3. ${literalTitle} · 2026-10-01 12:00–13:00`);
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
    await showPane(page, "일정");
    await timeline.getByRole("button", { name: new RegExp(literalTitle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) }).click();
    await showPane(page, "지도");
    await expect(thirdMarker).toHaveAttribute("aria-pressed", "true");
    await expect.poll(async () => (await readMapSdk(page))?.pans.at(-1)).toEqual({ lat: 37.57, lng: 127.01 });
    await firstMarker.click();
    await expect(firstMarker).toHaveAttribute("aria-pressed", "true");
    await showPane(page, "일정");
    await expect(timeline.locator('article[data-selected="true"]')).toContainText("첫 지도 장소");
    const previousPan = (await readMapSdk(page))?.pans.at(-1);
    await timeline.getByRole("button", { name: /좌표가 없는 중간 일정/ }).click();
    await showPane(page, "지도");
    await expect(firstMarker).toHaveAttribute("aria-pressed", "false");
    await expect(thirdMarker).toHaveAttribute("aria-pressed", "false");
    expect((await readMapSdk(page))?.pans.at(-1)).toEqual(previousPan);
    await firstMarker.focus();
    await firstMarker.press("Enter");
    await expect(firstMarker).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator("#trip-pane-map").getByRole("heading", { name: "첫 지도 장소", exact: true })).toBeVisible();

    await page.getByRole("button", { name: /2일차/ }).click();
    await expect(marker(page, "1. 다음 날 첫 장소 · 2026-10-02 09:00–10:00")).toBeVisible();
    await expect(marker(page, "2. 다음 날 둘째 장소 · 2026-10-02 10:00–11:00")).toBeVisible();
    await expect(firstMarker).toHaveCount(0);
    await expect.poll(async () => (await readMapSdk(page))?.markers.filter((item) => item.attached).map((item) => item.position)).toEqual([
      { lat: 37.52, lng: 126.97 },
      { lat: 37.51, lng: 127.02 },
    ]);
    await expect.poll(async () => (await readMapSdk(page))?.fits.at(-1)).toEqual([
      { lat: 37.52, lng: 126.97 },
      { lat: 37.51, lng: 127.02 },
    ]);

    await page.getByRole("button", { name: /3일차/ }).click();
    await expect(page.getByText("표시할 장소 좌표가 없어요.", { exact: true })).toBeVisible();
    await expect(region.locator("[data-sdk-marker]")).toHaveCount(0);
    await page.getByRole("button", { name: /1일차/ }).click();
    await expect(firstMarker).toBeVisible();
    await page.reload();
    await showPane(page, "지도");
    await expect(firstMarker).toBeVisible();
    await expect(thirdMarker).toBeVisible();
    expect(sdk.requests.every((request) => request.provider === provider)).toBe(true);
  });

  test("SDK 로드 실패를 알리고 재시도하면 같은 여행 지도를 복구한다", async ({ page, request }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    const sdk = await stubMapSdk(page, provider, { failFirst: true });
    await openMapTrip(page, request);
    const tripUrl = page.url();
    await showPane(page, "지도");
    const mapPane = page.locator("#trip-pane-map");
    await expect(mapPane.getByRole("alert")).toBeVisible();
    await expect(marker(page, "1. 첫 지도 장소 · 2026-10-01 09:00–10:00")).toHaveCount(0);
    expect(sdk.selectedRequestCount()).toBe(1);
    await page.getByRole("button", { name: "지도 다시 불러오기", exact: true }).click();
    await expect(marker(page, "1. 첫 지도 장소 · 2026-10-01 09:00–10:00")).toBeVisible();
    await expect(mapPane.getByRole("alert")).toHaveCount(0);
    await expect(page).toHaveURL(tripUrl);
    expect(sdk.selectedRequestCount()).toBe(2);
    expect(sdk.requests.every((request) => request.provider === provider)).toBe(true);
  });

  test("모바일에서 숨겨진 지도를 열 때 크기를 다시 계산하고 핀에서 일정 상세로 이동한다", async ({ page, request }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    const sdk = await stubMapSdk(page, provider);
    await openMapTrip(page, request);
    await expect(page.locator("#trip-pane-map")).not.toBeVisible();
    await showPane(page, "지도");
    const firstMarker = marker(page, "1. 첫 지도 장소 · 2026-10-01 09:00–10:00");
    await expect(firstMarker).toBeVisible();
    const initialResizes = (await readMapSdk(page))?.resizes ?? 0;
    await showPane(page, "일정");
    await page.setViewportSize({ width: 320, height: 812 });
    await showPane(page, "지도");
    await expect(firstMarker).toBeVisible();
    await expect.poll(async () => (await readMapSdk(page))?.resizes ?? 0).toBeGreaterThan(initialResizes);
    await noHorizontalScroll(page);
    await marker(page, `3. ${literalTitle} · 2026-10-01 12:00–13:00`).click();
    await page.locator("#trip-pane-map").getByRole("button", { name: "일정 상세 보기", exact: true }).click();
    await expect(page.getByRole("button", { name: "일정", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator('#trip-pane-schedule article[data-selected="true"]')).toContainText(literalTitle);
    await expect(page.locator("#trip-pane-schedule").getByRole("button", { name: new RegExp(literalTitle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) })).toHaveAttribute("aria-expanded", "true");
    expect(sdk.requests.every((request) => request.provider === provider)).toBe(true);
  });

  test("서버가 준 경로선을 SDK 선으로 그린다: 길 있는 구간은 실선, 직선으로 이은 구간은 점선이고 [경도, 위도] 순서가 좌표로 바로잡힌다", async ({ page, request }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await stubMapSdk(page, provider);
    await mockServer(request).scenario({ routeShapes: "on" });          // the default trip: 아침 식당 → 경복궁 (bus, straight line) and 경복궁 → 점심 식당 (walk, road graph)
    await start(page);
    await page.goto(`/trips/${TRIP_ID}`);
    await expect(page.getByRole("heading", { name: "나의 여행", exact: true })).toBeVisible();
    await showPane(page, "지도");
    await expect.poll(async () => (await readMapSdk(page))?.lines.filter((line) => line.attached).length).toBe(2);
    const drawn = (await readMapSdk(page))?.lines.filter((line) => line.attached) ?? [];
    const road = drawn.find((line) => !line.dashed)!, guess = drawn.find((line) => line.dashed)!;
    expect(road.path).toEqual([{ lat: 37.5796, lng: 126.977 }, { lat: 37.575, lng: 126.983 }, { lat: 37.57, lng: 126.99 }]);   // the server sent [lng, lat]
    expect(guess.path).toEqual([{ lat: 37.575, lng: 126.98 }, { lat: 37.5796, lng: 126.977 }]);
    await expect(page.locator("#trip-pane-map")).toContainText("경로선: 지도 데이터 © OpenStreetMap contributors (ODbL)");
    await expect(page.locator("#trip-pane-map")).toContainText("점선은 길을 몰라 두 곳을 직선으로 이은 구간이에요.");
    // another day: the lines of the first day are taken off the map
    await showPane(page, "일정");
    await page.getByRole("button", { name: /^2일차/ }).click();
    await showPane(page, "지도");
    await expect.poll(async () => (await readMapSdk(page))?.lines.filter((line) => line.attached).length).toBe(0);
  });

  test("「내 위치」(위치 동의가 있을 때): 누를 수 없는 표시와 정확도 원을 그리고, 위치가 바뀌면 같은 표시를 옮기며 500 m 보다 나쁜 원은 뺀다", async ({ page, request, context }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await allowLocation(context, { latitude: 37.575, longitude: 127, accuracy: 40 });
    await stubMapSdk(page, provider);
    await mockServer(request).scenario({ tripItems: "map" });
    await startWithLocationConsent(page, true);
    await page.goto(`/trips/${TRIP_ID}`);
    await expect(page.getByRole("heading", { name: "나의 여행", exact: true })).toBeVisible();
    await showPane(page, "지도");
    const region = page.getByRole("region", { name: "여행 지도", exact: true });
    const me = async () => (await readMapSdk(page))?.markers.filter((item) => item.attached && item.title === "내 위치").map((item) => item.position);
    await expect(region.getByRole("img", { name: "내 위치", exact: true })).toBeVisible();
    await expect.poll(me).toEqual([{ lat: 37.575, lng: 127 }]);
    await expect.poll(async () => (await readMapSdk(page))?.circles.filter((circle) => circle.attached).map((circle) => circle.radius)).toEqual([40]);
    await expect(region.getByRole("button", { name: /내 위치/ })).toHaveCount(0);                        // 핀이 아니다: 누르는 단추가 아니다
    await expect(marker(page, "1. 첫 지도 장소 · 2026-10-01 09:00–10:00")).toBeVisible();
    const fitsBefore = (await readMapSdk(page))?.fits.length ?? 0;
    await context.setGeolocation({ latitude: 37.58, longitude: 127.005, accuracy: 900 });
    await expect.poll(me, { timeout: 10_000 }).toEqual([{ lat: 37.58, lng: 127.005 }]);                // 같은 표시가 옮겨 갔다(하나 더 생기지 않았다)
    await expect.poll(async () => (await readMapSdk(page))?.circles.filter((circle) => circle.attached)).toEqual([]);
    expect((await readMapSdk(page))?.fits.length ?? 0).toBe(fitsBefore);                               // 지도는 고객을 쫓아 다시 맞추지 않는다
  });
});
