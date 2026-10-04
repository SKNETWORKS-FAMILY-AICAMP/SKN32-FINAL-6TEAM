import { expect, test, type Page } from "@playwright/test";
import { mockServer, start, TRIP_ID } from "./helpers";

/**
 * `[2026-10-04]` The lines between stops on the trip's map (`GET /v1/web/trips/{id}/route-shapes`, mobility session). The free map (OpenStreetMap, drawn with
 * Leaflet) is the build these tests run on; the Naver and Google drawing is in `maps.spec.ts`. mock 서버 시험이다 — 화면이 무엇을 그리고 무엇을 말하는지를 본다.
 * ★What the screen must say: the data source (ODbL) whenever a line is drawn; a line made of a guess is dashed and pale; subway and bus lines are not real tracks.
 */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const lines = (page: Page) => page.locator("#trip-pane-map path.trip-route-line");
const caption = (page: Page) => page.locator("#trip-pane-map");

async function openMap(page: Page) {
  await start(page);
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(page.getByRole("heading", { name: "나의 여행", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "지도", exact: true }).click();
  await expect(page.locator("#trip-pane-map .leaflet-marker-icon").first()).toBeVisible();
}

test("선이 있는 여행: 길을 아는 구간은 실선, 직선으로 이은 구간은 점선·옅은 색으로 그리고, 출처와 점선·버스의 뜻을 지도 아래에 적는다", async ({ page, request }) => {
  await mockServer(request).scenario({ routeShapes: "on" });
  await openMap(page);
  await expect(lines(page)).toHaveCount(2);
  const solid = page.locator("#trip-pane-map path.trip-route-line:not(.trip-route-line--dashed)");
  const dashed = page.locator("#trip-pane-map path.trip-route-line--dashed");
  await expect(solid).toHaveCount(1);
  await expect(dashed).toHaveCount(1);
  // a guess is dashed and paler than a real road
  expect(await dashed.getAttribute("stroke-dasharray")).toBeTruthy();
  expect(await solid.getAttribute("stroke-dasharray")).toBeNull();
  expect(Number(await dashed.getAttribute("stroke-opacity"))).toBeLessThan(Number(await solid.getAttribute("stroke-opacity")));
  // the line goes through every point the server sent, in order: the first and the last are the two places around the move
  const route = await solid.getAttribute("d");
  expect(route?.match(/[ML]/g)?.length).toBe(3);

  const text = await caption(page).innerText();
  expect(text).toContain("경로선: 지도 데이터 © OpenStreetMap contributors (ODbL)");   // the data source, as the server wrote it
  expect(text).toContain("점선은 길을 몰라 두 곳을 직선으로 이은 구간이에요.");
  expect(text).toContain("버스는 정류장 정보가 없어 직선으로 이어요.");
  expect(text).toContain("아침 식당 → 경복궁: 정류장 정보가 없어 직선으로 이었어요");   // the server own reason for that guess (its `note`), as it wrote it
  expect(text).not.toContain("실제 선로 모양이 아니에요");                                // no subway line is on this map

  // the pins stay pressable and the lines do not cover them
  await expect(page.locator("#trip-pane-map .leaflet-marker-icon")).not.toHaveCount(0);
});

test("서버에 이 경로가 아직 없으면(404) 선도 출처 문구도 오류 문구도 없이 핀만 보인다", async ({ page }) => {
  await openMap(page);                                                 // default scenario: routeShapes "off" → FastAPI 404 {detail}
  await expect(lines(page)).toHaveCount(0);
  const text = await caption(page).innerText();
  expect(text).not.toContain("ODbL");
  expect(text).not.toContain("경로선을 불러오지 못했어요");
  await expect(page.locator("#trip-pane-map .leaflet-marker-icon").first()).toBeVisible();
});

test("선을 읽다 실패하면(500) 읽지 못했다고 말하고 핀은 그대로 보인다 — 선이 없다는 말이 아니다", async ({ page, request }) => {
  await mockServer(request).scenario({ routeShapes: "fail" });
  await openMap(page);
  await expect(caption(page)).toContainText("경로선을 불러오지 못했어요");
  await expect(lines(page)).toHaveCount(0);
  await expect(page.locator("#trip-pane-map .leaflet-marker-icon").first()).toBeVisible();
});

test("서버가 선을 늦게 줘도(길 자료를 올리는 중) 핀이 먼저 보이고, 선은 오면 그려진다", async ({ page, request }) => {
  await mockServer(request).scenario({ routeShapes: "slow" });
  await openMap(page);
  await expect(lines(page)).toHaveCount(0);                            // not there yet — but the map is already usable
  await expect(page.locator("#trip-pane-map .leaflet-marker-icon").first()).toBeVisible();
  await expect(lines(page)).toHaveCount(2, { timeout: 15_000 });
});

test("다른 날로 바꾸면 그 날 장소 사이의 선만 남는다(둘째 날에는 선이 없다)", async ({ page, request }) => {
  await mockServer(request).scenario({ routeShapes: "on" });
  await openMap(page);
  await expect(lines(page)).toHaveCount(2);
  await page.getByRole("button", { name: "일정", exact: true }).click();
  await page.getByRole("button", { name: /^2일차/ }).click();
  await page.getByRole("button", { name: "지도", exact: true }).click();
  await expect(lines(page)).toHaveCount(0);
  await expect(caption(page)).not.toContainText("ODbL");               // no line, no data-source line
});
