import { expect, test, type Locator, type Page } from "@playwright/test";
import { mockServer, TRIP_ID } from "./helpers";
import { allowLocation, changeLocationConsent, countLocationAsks, locationAsks, north, setPageHidden, startWithLocationConsent } from "./location-kit";
import { INTAKE, needsBadge } from "./plan-check-kit";

/**
 * mock 서버 시험(화면 반응) — 실서버 확인(서버 응답)은 따로.
 *
 * `[2026-10-05 사용자 지시]` 「지도가 나올 때 고객의 위치를 지도에 바로 표시」 · 「서버에서 고객이 정확히 어느 지점에서 멈춘 건지 체크」의 웹 몫
 * (계약 초안 `wiki/records/plans/2026-10-05_동의기록_위치수집_백엔드_요청.md` §2·§3). 무료 지도(OpenStreetMap, Leaflet) 빌드에서 돈다 —
 * 네이버·구글은 `maps.spec.ts`(SDK 계약 대역)가 본다. 브라우저 위치는 Playwright 가 흉내 낸 값(`context.setGeolocation`)이다.
 *   - 위치 동의가 있을 때만: 지도가 붙자마자 위치를 읽어 「내 위치」(파란 점 + 정확도 원)를 그리고 따라간다. 없으면 묻지도 그리지도 보내지도 않는다.
 *   - 여행 화면(여행 번호가 있는 지도)만 서버로 위치 점을 보낸다(`POST …/location`, 30 m · 60 초 규칙, 숨겨질 때 한꺼번에). 계획 확인 화면은 보내지 않는다.
 *   - 「모든 일정 보기」는 핀만 맞춘다. 핀이 없는 날은 내 위치로 가운데를 맞춘다.
 *   - 서버가 머문 곳을 주면 회색 점으로 올린다. 주지 않으면(옛 서버 404) 아무것도 그리지 않는다.
 */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

/** 기본 여행의 첫날: 아침 식당 (37.575, 126.98) · 경복궁 관람 (37.5796, 126.977) · 점심 식당 (37.57, 126.99). 이 사이의 한 점. */
const NEAR = { latitude: 37.5765, longitude: 126.979 };
const LOCATION_POST = `/trips/${TRIP_ID}/location`;

const mapPane = (page: Page) => page.locator("#trip-pane-map");
const meDot = (scope: Page | Locator) => scope.getByRole("img", { name: "내 위치", exact: true });
const tripPin = (page: Page, label: string) => mapPane(page).locator(`.leaflet-marker-icon[title^="${label}"]`);
const notice = (page: Page) => page.locator("[data-my-location-notice]");
const posts = async (request: Parameters<typeof mockServer>[0]) => mockServer(request).received("POST", LOCATION_POST);
type Fix = { lat: number; lng: number; accuracy_m?: number; at: string };
const fixesOf = (entry: { body: Record<string, unknown> | null }) => (entry.body as { fixes: Fix[] }).fixes;

/** 여행 화면을 열고 지도 탭으로 간다. `agreed`: 위치 동의(필수 둘은 늘 동의). */
async function openTripMap(page: Page, agreed: boolean) {
  await startWithLocationConsent(page, agreed);
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(page.getByRole("heading", { name: "나의 여행", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "지도", exact: true }).click();
  await expect(mapPane(page).locator(".leaflet-marker-icon[title]").first()).toBeVisible();
}

/** 지도가 움직임을 멈출 때까지(처음 맞추기·이동 애니메이션) 기다린다 — 그 뒤에 잰다. */
async function settled(target: Locator) {
  const where = async () => { const box = await target.boundingBox(); return box ? `${Math.round(box.x)},${Math.round(box.y)}` : "none"; };
  await expect.poll(async () => { const one = await where(); await target.page().waitForTimeout(400); return one === (await where()); }, { timeout: 10_000 }).toBe(true);
}

test("위치 동의가 있으면 여행 지도를 열자마자 「내 위치」가 파란 점과 정확도 원으로 보이고, 점은 누름을 받지 않아 같은 자리의 핀이 그대로 눌린다", async ({ page, context }) => {
  await allowLocation(context, { latitude: 37.5796, longitude: 126.977, accuracy: 25 });          // 경복궁 관람 핀이 선 바로 그 자리
  await openTripMap(page, true);
  const dot = meDot(mapPane(page));
  await expect(dot).toBeVisible();
  await expect(mapPane(page).locator("path.my-location-accuracy")).toHaveCount(1);                 // 25 m 정확도 원
  await expect(mapPane(page).getByRole("button", { name: /내 위치/ })).toHaveCount(0);             // 핀(누르는 단추)이 아니다
  await expect(dot).toHaveText("");                                                                 // 번호가 없다(핀은 번호 물방울)
  expect(await dot.locator("span").evaluate((element) => getComputedStyle(element).borderRadius)).toBe("50%");   // 둥근 점
  await settled(dot);
  // 점 한가운데를 눌러도 점이 받지 않는다(누름은 그 밑으로 간다)
  const takesPress = await dot.evaluate((element) => {
    const box = element.getBoundingClientRect();
    const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
    return Boolean(hit && element.contains(hit));
  });
  expect(takesPress).toBe(false);
  // 같은 자리의 핀은 그대로 눌린다 — 점이 가리지 않는다(실제 클릭: 가리는 것이 있으면 Playwright 가 누르지 못한다)
  await tripPin(page, "2. 경복궁 관람").locator("[data-pin-body]").click();
  await expect(tripPin(page, "2. 경복궁 관람")).toHaveAttribute("aria-pressed", "true");
  await expect(mapPane(page).getByRole("heading", { name: "경복궁 관람", exact: true })).toBeVisible();
  await expect(notice(page)).toHaveCount(0);                                                        // 위치를 찾았으니 할 말이 없다
});

test("위치 동의가 없으면 브라우저에 위치를 묻지도, 점을 그리지도, 서버로 보내지도 않고 아무 말도 하지 않는다", async ({ page, context, request }) => {
  await mockServer(request).scenario({ location: "on" });
  await allowLocation(context, NEAR);                                                               // 브라우저는 답할 수 있다 — 화면이 묻지 않아야 한다
  await countLocationAsks(page);
  await openTripMap(page, false);
  await page.waitForTimeout(1_500);
  expect(await locationAsks(page)).toBe(0);
  await expect(meDot(page)).toHaveCount(0);
  await setPageHidden(page, true);                                                                  // 숨겨질 때가 보내는 때 — 그래도 아무것도 안 간다
  await page.waitForTimeout(800);
  expect((await mockServer(request).log()).filter((entry) => entry.path.includes("/location"))).toEqual([]);
  await expect(notice(page)).toHaveCount(0);
});

test("브라우저 위치 권한이 꺼져 있으면 점 없이 지도 아래 안내줄에 한 줄로 알린다", async ({ page, context }) => {
  await context.clearPermissions();                                                                 // 허용하지 않은 위치 요청은 자동 화면 브라우저가 거절한다
  await openTripMap(page, true);
  await expect(notice(page)).toContainText("위치 권한이 꺼져 있어 내 위치를 못 보여 드려요");
  await expect(notice(page)).toHaveCount(1);
  await expect(meDot(page)).toHaveCount(0);
  await expect(tripPin(page, "1. 아침 식당")).toBeVisible();                                         // 지도와 핀은 그대로
});

test("이미 거절된 권한이면 다시 묻지 않고(위치 호출 0번) 바로 안내줄로 알린다", async ({ page }) => {
  await page.addInitScript(() => {
    const query = navigator.permissions.query.bind(navigator.permissions);
    navigator.permissions.query = (descriptor: PermissionDescriptor) => descriptor.name === "geolocation"
      ? Promise.resolve({ state: "denied", name: "geolocation", onchange: null, addEventListener() {}, removeEventListener() {}, dispatchEvent: () => true } as unknown as PermissionStatus)
      : query(descriptor);
  });
  await countLocationAsks(page);
  await openTripMap(page, true);
  await expect(notice(page)).toContainText("위치 권한이 꺼져 있어 내 위치를 못 보여 드려요");
  expect(await locationAsks(page)).toBe(0);
  await expect(meDot(page)).toHaveCount(0);
});

test("위치가 바뀌면 점이 따라 움직이고(지도는 따라가지 않는다), 정확도가 500 m 보다 나쁘면 원은 빼고 점만 둔다", async ({ page, context }) => {
  await allowLocation(context, { ...NEAR, accuracy: 25 });
  await openTripMap(page, true);
  const dot = meDot(mapPane(page));
  await expect(dot).toBeVisible();
  await settled(dot);
  const before = (await dot.boundingBox())!;
  const pin = tripPin(page, "1. 아침 식당");
  const pinBefore = (await pin.boundingBox())!;
  await context.setGeolocation({ latitude: NEAR.latitude, longitude: 126.983, accuracy: 900 });    // 동쪽으로 약 350 m
  await expect.poll(async () => (await dot.boundingBox())!.x - before.x, { timeout: 10_000 }).toBeGreaterThan(20);
  await expect(mapPane(page).locator("path.my-location-accuracy")).toHaveCount(0);
  await expect(meDot(mapPane(page))).toHaveCount(1);                                                // 옮겨졌지 하나 더 생기지 않았다
  const pinAfter = (await pin.boundingBox())!;
  expect(Math.abs(pinAfter.x - pinBefore.x) + Math.abs(pinAfter.y - pinBefore.y)).toBeLessThan(2);  // 지도는 고객을 쫓아 움직이지 않는다
});

test("여행 화면은 읽은 위치를 서버에 보낸다 — 모았다가 화면이 숨겨질 때 한꺼번에, 30 m 안쪽 움직임은 새 점이 아니고 같은 점은 다시 가지 않는다", async ({ page, context, request }) => {
  await mockServer(request).scenario({ location: "on" });
  await allowLocation(context, { ...NEAR, accuracy: 25 });
  await openTripMap(page, true);
  const dot = meDot(mapPane(page));
  await expect(dot).toBeVisible();
  await setPageHidden(page, true);
  await expect.poll(async () => (await posts(request)).length).toBe(1);
  const [first] = await posts(request);
  const sent = fixesOf(first);
  expect(sent).toHaveLength(1);
  expect(sent[0].lat).toBeCloseTo(NEAR.latitude, 5);
  expect(sent[0].lng).toBeCloseTo(NEAR.longitude, 5);
  expect(sent[0].accuracy_m).toBe(25);
  expect(Number.isFinite(Date.parse(sent[0].at))).toBe(true);
  expect(first.csrf).toBeTruthy();                                                                   // 쓰기는 세션의 보안 토큰과 함께
  expect(first.path).not.toMatch(/37\.|126\./);                                                      // ★위치는 주소에 싣지 않는다

  await setPageHidden(page, false);
  await settled(dot);
  const start10 = (await dot.boundingBox())!;
  await context.setGeolocation({ latitude: north(NEAR.latitude, 10), longitude: NEAR.longitude, accuracy: 25 });    // 10 m: 점은 움직여도 서버엔 새 점이 아니다
  await page.waitForTimeout(2_500);
  await context.setGeolocation({ latitude: north(NEAR.latitude, 100), longitude: NEAR.longitude, accuracy: 25 });   // 100 m: 새 점
  await expect.poll(async () => start10.y - (await dot.boundingBox())!.y, { timeout: 10_000 }).toBeGreaterThan(8);             // 100 m 는 확대 수준에 따라 10~30px 다(고정 20px 는 지도의 처음 확대에 기댄 값이었다)
  await setPageHidden(page, true);
  await expect.poll(async () => (await posts(request)).length).toBe(2);
  const again = fixesOf((await posts(request))[1]);
  expect(again).toHaveLength(1);                                                                     // 10 m 점은 없고, 처음 점은 다시 가지 않았다
  expect(again[0].lat).toBeCloseTo(north(NEAR.latitude, 100), 5);
  expect(again[0].at).not.toBe(sent[0].at);
});

test("서버가 위치 동의가 없다고 하면(403 consent_required) 더는 보내지 않는다", async ({ page, context, request }) => {
  await mockServer(request).scenario({ location: "no_consent" });
  await allowLocation(context, NEAR);
  await openTripMap(page, true);
  await expect(meDot(mapPane(page))).toBeVisible();
  await setPageHidden(page, true);
  await expect.poll(async () => (await posts(request)).length).toBe(1);
  await setPageHidden(page, false);
  await context.setGeolocation({ latitude: north(NEAR.latitude, 150), longitude: NEAR.longitude, accuracy: 20 });
  await page.waitForTimeout(3_000);
  await setPageHidden(page, true);
  await page.waitForTimeout(1_000);
  expect(await posts(request)).toHaveLength(1);
  await expect(page.getByRole("alert").filter({ hasText: /위치|동의/ })).toHaveCount(0);            // 오류를 화면에 띄우지 않는다
});

test("서버에 위치 받기가 없으면(옛 서버 404) 조용히 멈춘다 — 오류 문구도 다시 보내기도 없다", async ({ page, context, request }) => {
  await allowLocation(context, NEAR);                                                                // 기본 장면: location "off"
  await openTripMap(page, true);
  await expect(meDot(mapPane(page))).toBeVisible();                                                  // 점은 그대로 보인다(그리는 것은 서버와 상관없다)
  await setPageHidden(page, true);
  await expect.poll(async () => (await posts(request)).length).toBe(1);
  await setPageHidden(page, false);
  await context.setGeolocation({ latitude: north(NEAR.latitude, 150), longitude: NEAR.longitude, accuracy: 20 });
  await page.waitForTimeout(3_000);
  await setPageHidden(page, true);
  await page.waitForTimeout(1_000);
  expect(await posts(request)).toHaveLength(1);
  await expect(mapPane(page).locator("[data-stay-point]")).toHaveCount(0);
  await expect(page.getByRole("alert").filter({ hasText: /\S/ })).toHaveCount(0);      // 내용이 있는 알림은 없다(경로 안내용 빈 알림 영역은 늘 있다)
});

test("위치 동의를 끄면 점이 바로 사라지고 더는 위치를 따라가지 않는다", async ({ page, context }) => {
  await allowLocation(context, NEAR);
  await openTripMap(page, true);
  await expect(meDot(mapPane(page))).toBeVisible();
  await changeLocationConsent(page, false);
  await expect(meDot(page)).toHaveCount(0);
  await context.setGeolocation({ latitude: north(NEAR.latitude, 200), longitude: NEAR.longitude });
  await page.waitForTimeout(2_500);
  await expect(meDot(page)).toHaveCount(0);
  await expect(notice(page)).toHaveCount(0);
});

test("계획 확인 화면의 지도에도 「내 위치」가 보이지만, 여행 번호가 없으니 서버로 보내지도 머문 곳을 묻지도 않는다", async ({ page, context, request }) => {
  const server = mockServer(request);
  await server.scenario({ review: "on", board: "rich", readingPolls: 0, location: "on" });
  await allowLocation(context, { latitude: 37.5765, longitude: 126.985 });
  await startWithLocationConsent(page, true);
  await page.goto(`/intakes/${INTAKE}`);
  await expect(needsBadge(page)).toBeVisible();
  await expect(meDot(page)).toHaveCount(1);
  await expect(meDot(page)).toBeVisible();
  await setPageHidden(page, true);
  await page.waitForTimeout(1_000);
  expect((await server.log()).filter((entry) => entry.path.includes("/location"))).toEqual([]);
});

test("「모든 일정 보기」는 핀만 맞춘다 — 멀리 있는 내 위치 때문에 핀이 작아지지 않는다", async ({ page, context }) => {
  await allowLocation(context, { latitude: 35.1796, longitude: 129.0756 });                          // 부산: 서울의 일정과 멀다
  await openTripMap(page, true);
  const dot = meDot(mapPane(page));
  await expect(dot).toHaveCount(1);
  const map = page.getByRole("region", { name: "여행 지도", exact: true });
  const zoom = mapPane(page).locator(".leaflet-control-zoom");
  await map.hover({ position: { x: 200, y: 120 } });                                                 // 단추는 지도에 포인터가 있을 때 보인다
  await zoom.getByRole("button", { name: "Zoom out" }).click();
  await zoom.getByRole("button", { name: "Zoom out" }).click();
  await zoom.getByRole("button", { name: "모든 일정 보기" }).click();
  for (const label of ["1. 아침 식당", "2. 경복궁 관람", "3. 점심 식당"]) await expect(tripPin(page, label)).toBeInViewport();
  await expect(dot).not.toBeInViewport();                                                            // 내 위치는 맞추기에 들지 않는다
  await settled(tripPin(page, "3. 점심 식당"));
  const first = (await tripPin(page, "1. 아침 식당").boundingBox())!, last = (await tripPin(page, "3. 점심 식당").boundingBox())!;
  expect(Math.hypot(last.x - first.x, last.y - first.y)).toBeGreaterThan(100);                      // 핀이 한 점으로 쪼그라들지 않았다
});

test("핀이 하나도 없는 날은 내 위치로 지도 가운데를 맞춘다", async ({ page, context, request }) => {
  await mockServer(request).scenario({ tripItems: "map" });                                         // 셋째 날은 좌표가 있는 일정이 없다
  await allowLocation(context, { latitude: 37.5512, longitude: 126.9882 });
  await openTripMap(page, true);
  await page.getByRole("button", { name: /3일차/ }).click();
  await expect(page.getByText("표시할 장소 좌표가 없어요.", { exact: true })).toBeVisible();
  const dot = meDot(mapPane(page));
  await dot.scrollIntoViewIfNeeded();                                                               // 지도는 이 화면의 아래쪽에 있다
  await expect(dot).toBeInViewport();
  const box = (await page.getByRole("region", { name: "여행 지도", exact: true }).boundingBox())!;
  await expect.poll(async () => {
    const at = (await dot.boundingBox())!;
    return Math.abs(at.x + at.width / 2 - (box.x + box.width / 2)) + Math.abs(at.y + at.height / 2 - (box.y + box.height / 2));
  }, { timeout: 8_000 }).toBeLessThan(30);
});

test("서버가 머문 곳을 알려 주면 그날 지도에 회색 점으로 올린다 — 가까운 일정 이름과 시각을 읽어 주고, 다른 날에는 없다", async ({ page, context, request }) => {
  await mockServer(request).scenario({ location: "stops" });
  await allowLocation(context, NEAR);
  await openTripMap(page, true);
  const stay = mapPane(page).getByRole("img", { name: "머문 곳 · 경복궁 관람 근처 · 09:32–10:50", exact: true });
  await expect(stay).toHaveCount(1);
  await expect.poll(async () => (await mockServer(request).received("GET", `/trips/${TRIP_ID}/location/stops`)).length).toBeGreaterThan(0);
  await page.getByRole("button", { name: /^2일차/ }).click();
  await expect(mapPane(page).locator("[data-stay-point]")).toHaveCount(0);
  await page.getByRole("button", { name: /^1일차/ }).click();
  await expect(stay).toHaveCount(1);
});

test("위치 동의가 없으면 서버가 머문 곳을 갖고 있어도 묻지도 그리지도 않는다", async ({ page, request }) => {
  await mockServer(request).scenario({ location: "stops" });
  await openTripMap(page, false);
  await page.waitForTimeout(1_500);
  await expect(mapPane(page).locator("[data-stay-point]")).toHaveCount(0);
  expect(await mockServer(request).received("GET", `/trips/${TRIP_ID}/location/stops`)).toEqual([]);
});
