import { expect, test } from "@playwright/test";
import { checkPlan, mockServer, start } from "./helpers";
import { card, mapSettled, needsBadge, openFinished, pin, sheet, type Json } from "./plan-check-kit";

/**
 * `[2026-10-06 사용자 지시]` 계획 확인 화면: 핀을 누르면 목록의 해당 일정만 열기 · 경로선을 누르면 그 구간 설명 + 목록의 이동 줄 열기 · 핀 선과 점은 핀 몸통 아래 층 · 「전체 · 1일차 · 2일차」 줄이 「계획 확인」 줄과 한 줄 ·
 * 확인이 끝나면 목록이 맨 위에서 시작 · 카드 제목과 같은 줄의 도구가 제목 폭을 무너뜨리지 않음 · 이름 수정 버튼 오른쪽 여백. 테스트용 mock 서버로 도는 자동 시험이다(화면 반응을 본다 — 실서버 확인 아님).
 */
const DAY_TWO_STOP: Json = {
  id: "0-3", source_id: "s1", index: 3, title: "N서울타워", kind: "activity", day: 2, date: "2026-10-02", starts_at: "10:00", ends_at: "11:30",
  locked: false, status: "keep", can_lock: true, place_state: "found", candidates_hint: null,
  place: { name: "N서울타워", latitude: 37.5512, longitude: 126.9882, source: "tour_api", kind: null, content_id: null, content_type_id: null },
  rows: [{ row: "place", result: "ok", text: "관광공사 정보로 찾았어요" }],
};
/** ★2026-10-06 사용자 지시: 경로선 설명은 공통 알림 막대를 사용한다. 마커 설명 알림은 2026-10-08 사용자 지시로 제거했다. */
const callout = (page: import("@playwright/test").Page, text: RegExp | string) => page.getByRole("status").filter({ hasText: text });
const device = (page: import("@playwright/test").Page) => page.locator('[data-device]').first();
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

test("마커는 해당 일정만 열고 중복 설명 알림을 띄우지 않는다 — 다른 마커와 재선택도 같다", async ({ page, request }) => {
  await openFinished(page, request);
  await pin(page, "2.").locator("[data-pin-body]").click();
  await expect(card(page, "올리브영").getByRole("heading").getByRole("button")).toHaveAttribute("aria-expanded", "true");
  await expect(callout(page, /^2올리브영/)).toHaveCount(0);
  await expect(pin(page, "2.")).toHaveAttribute("aria-pressed", "true");
  await mapSettled(page);
  // 거리 칩으로 교대된 마커를 억지로 누르지 않고 전체 보기로 먼저 지도 안에 넣는다.
  await page.getByRole("region", { name: "여행 지도", exact: true }).hover();
  await page.getByRole("button", { name: "지도 단추 펼치기", exact: true }).click();
  await page.getByRole("button", { name: "모든 일정 보기", exact: true }).click();
  await mapSettled(page);
  // 작은 지도에서는 펼쳐진 지도 단추를 접은 뒤 그 아래 마커를 고른다.
  await page.getByRole("button", { name: "지도 단추 접기", exact: true }).click();
  await pin(page, "1.").locator("[data-pin-body]").click();
  await expect(card(page, "경복궁 관람").getByRole("heading").getByRole("button")).toHaveAttribute("aria-expanded", "true");
  await expect(callout(page, /^1경복궁 관람/)).toHaveCount(0);
  await mapSettled(page);
  await pin(page, "1.").locator("[data-pin-body]").click();
  await expect(pin(page, "1.")).toHaveAttribute("aria-pressed", "false");
});

test("경로 설명 알림은 하얀 카드다: 휴대폰 틀 안 머리줄 아래, 틀 폭에 맞고 테두리 빛 · 고리 움직임이 한 번 지나가며, 몇 초 뒤 저절로 사라지고 단추 위에 있는 동안은 남는다", async ({ page, request }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await openFinished(page, request, undefined, { intakeRoutes: "on" });
  await page.locator("path.trip-route-hit").first().dispatchEvent("click");
  const note = callout(page, /^→경복궁 관람 → 올리브영/);
  await expect(note).toBeVisible();
  // 하얀 카드를 눈에 띄게 하는 강조: 테두리를 도는 빛과 한 번 퍼지는 고리가 나타날 때 지나간다
  const names = await note.evaluate((element) => element.getAnimations({ subtree: true }).map((animation) => (animation as CSSAnimation).animationName));
  expect(names.some((name) => name.includes("toastShine"))).toBe(true);
  expect(names.some((name) => name.includes("toastRing"))).toBe(true);
  await page.waitForTimeout(450);                                                                       // 들어오는 움직임이 끝나도록
  const [frame, bar] = [(await device(page).boundingBox())!, (await note.boundingBox())!];
  expect(Math.abs(bar.x - (frame.x + 12))).toBeLessThanOrEqual(1);                                       // 틀 폭에서 양쪽 12px 안
  expect(Math.abs(bar.width - (frame.width - 12 - 68))).toBeLessThanOrEqual(3);                          // 지도 화면: 오른쪽 지도 단추 자리(68px)를 비운다. 틀 가장자리 선(1px)만큼은 오차
  expect(Math.abs(bar.y - (frame.y + 76))).toBeLessThanOrEqual(2);                                       // 모든 알림이 같은 자리(머리줄 바로 아래)
  const look = await note.evaluate((element) => { const style = getComputedStyle(element); return { background: style.backgroundColor, size: style.fontSize }; });
  expect(look.size).toBe("13px");
  expect(look.background).not.toBe("rgba(0, 0, 0, 0)");
  await expect(note.getByRole("button", { name: "목록에서 보기" })).toBeVisible();
  await note.getByRole("button", { name: "목록에서 보기" }).hover();                                             // 읽는 동안(단추 위에 포인터가 있는 동안)은 남는다
  await page.waitForTimeout(8500);
  await expect(note).toBeVisible();
  await page.mouse.move(frame.x + 5, frame.y + 300);
  await expect(note).toHaveCount(0, { timeout: 12_000 });                                                // 떠나면 몇 초 뒤 사라진다
});

test("경로선을 누르면 그 구간이 골라지고 — 설명 알림(어디서 어디로 · 수단 · 출발과 도착) · 목록의 이동 줄이 열림 — 다시 누르면 놓는다", async ({ page, request }) => {
  await openFinished(page, request, undefined, { intakeRoutes: "on" });
  const hit = page.locator("path.trip-route-hit");
  await expect(hit).toHaveCount(2);
  await hit.first().dispatchEvent("click");
  const note = callout(page, /^→경복궁 관람 → 올리브영/);
  await expect(note).toBeVisible();
  await expect(note).toContainText("지하철 3호선");
  await expect(note).toContainText("10:30 출발");
  await expect(page.locator('li[data-type="move"][data-entry-id] [aria-expanded="true"]').first()).toBeVisible();   // 목록의 이동 줄이 열렸다
  const widths = await page.locator("path.trip-route-line").evaluateAll((paths) => paths.map((path) => Number(path.getAttribute("stroke-width"))));
  expect(Math.max(...widths)).toBeGreaterThanOrEqual(7);                                                // 고른 선은 더 굵다(점선 4 → 7)
  await hit.first().dispatchEvent("click");                                                                          // 다시 누르면 놓는다
  await expect(note).toHaveCount(0);
});

test("경로선을 눌러 고른 뒤 목록의 그 이동 줄을 다시 눌러 닫으면 지도의 선도 놓인다 — 목록에서 열면 지도의 선이 골라진다", async ({ page, request }) => {
  // `[2026-10-07 사용자 지적]` 목록에서는 풀렸는데 지도에서는 클릭 상태가 안 풀렸다
  await openFinished(page, request, undefined, { intakeRoutes: "on" });
  const widest = async () => Math.max(...await page.locator("path.trip-route-line").evaluateAll((paths) => paths.map((path) => Number(path.getAttribute("stroke-width")))));
  await page.locator("path.trip-route-hit").first().dispatchEvent("click");
  await expect.poll(widest).toBeGreaterThanOrEqual(7);
  const open = page.locator('li[data-type="move"][data-entry-id="0-0:0-1"] [aria-expanded="true"]');
  await expect(open).toBeVisible();
  await open.click();                                                                                   // 목록에서 닫는다
  await expect.poll(widest).toBeLessThan(7);                                                           // 지도의 선도 놓였다
  await page.locator('li[data-type="move"][data-entry-id="0-0:0-1"] [aria-expanded="false"]').click(); // 목록에서 연다
  await expect.poll(widest).toBeGreaterThanOrEqual(7);                                                 // 지도의 선이 골라진다
});

test("지도의 「! n」을 누르면 목록은 확인 필요만, 지도는 확인 필요 핀만 주황으로 남고 나머지 핀은 회색(눌리지 않음) — 다시 누르면 돌아온다", async ({ page, request }) => {
  // `[2026-10-07 사용자 지시]`
  await openFinished(page, request);
  const tones = () => page.locator(".leaflet-marker-icon").evaluateAll((icons) => icons.map((icon) => `${(icon.getAttribute("title") ?? "").slice(0, 2)}${(icon.querySelector("[data-tone]") as HTMLElement | null)?.dataset.tone ?? (icon as HTMLElement).dataset.tone ?? "-"}`));
  await page.getByRole("button", { name: /^확인 필요 \d+곳$/ }).click();
  await expect(page.getByText("확인이 필요한 곳만 보는 중이에요")).toBeVisible();
  await expect.poll(tones).toEqual(expect.arrayContaining(["1.muted", "2.warn", "3.muted"]));
  await page.getByRole("button", { name: /^확인 필요 \d+곳$/ }).click();
  await expect(page.getByText("확인이 필요한 곳만 보는 중이에요")).toHaveCount(0);
  await expect.poll(async () => (await tones()).some((tone) => tone.endsWith("muted") || tone.endsWith("warn"))).toBe(false);
});

test("핀을 누르면 경로 선택은 풀리고, 경로를 누르면 핀 선택이 풀린다(둘은 한 번에 하나) — 알림도 하나만 선다", async ({ page, request }) => {
  await openFinished(page, request, undefined, { intakeRoutes: "on" });
  await pin(page, "2.").locator("[data-pin-body]").click();
  await expect(callout(page, /^2올리브영/)).toHaveCount(0);
  await page.locator("path.trip-route-hit").first().dispatchEvent("click");
  await expect(callout(page, /^→경복궁 관람 → 올리브영/)).toBeVisible();
  await expect(callout(page, /^2올리브영/)).toHaveCount(0);
  await mapSettled(page);
  await pin(page, "3.").locator("[data-pin-body]").click();
  await expect(callout(page, /^3/)).toHaveCount(0);
  await expect(callout(page, /^→경복궁 관람 → 올리브영/)).toHaveCount(0);
});

test("핀을 밀어낸 선과 점은 핀 몸통보다 아래 층에 따로 있다(다른 핀의 몸통 위로 그려지지 않는다)", async ({ page, request }) => {
  await openFinished(page, request);
  const layers = await page.evaluate(() => {
    const z = (selector: string) => Number(getComputedStyle(document.querySelector(selector)!).zIndex);
    return { leaders: z(".leaflet-pinLeaders-pane"), markers: z(".leaflet-marker-pane"), routes: z(".leaflet-routes-pane"), leaderCount: document.querySelectorAll(".leaflet-pinLeaders-pane .leaflet-marker-icon").length, pinCount: document.querySelectorAll(".leaflet-marker-pane [data-pin-body]").length, bodiesInLeaderPane: document.querySelectorAll(".leaflet-pinLeaders-pane [data-pin-body]").length };
  });
  expect(layers.leaders).toBeLessThan(layers.markers);
  expect(layers.leaders).toBeGreaterThan(layers.routes);
  expect(layers.pinCount).toBe(3);
  expect(layers.leaderCount).toBe(3);                                                                   // 핀마다 선·점 칸이 하나씩, 층은 따로
  expect(layers.bodiesInLeaderPane).toBe(0);
});

test("이틀 이상이면 「전체 · 1일차 · 2일차」 칩이 목록 위에 투명하게 뜨고(따로 줄 · 경계선 없음), 「확인 필요」는 지도 쪽에 있다", async ({ page, request }) => {
  await openFinished(page, request, (view) => { view.review.items.push(DAY_TWO_STOP); });
  const head = page.locator("header").filter({ has: page.getByRole("tablist", { name: "일차 고르기" }) });
  await expect(head).toHaveCount(1);
  await expect(head.getByRole("tab")).toHaveText([/^전체$/, /^1일차/, /^2일차/]);
  // `[2026-10-07 사용자 지시]` 「! n」(확인 필요)은 지도 쪽으로 옮겼다 — 머리에는 없고 지도 위에 있다. 머리는 목록 위에 투명하게 떠 있다(경계선 없음)
  await expect(head.getByRole("button", { name: /^확인 필요 \d+곳$/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^확인 필요 \d+곳$/ })).toBeVisible();
  expect(await head.evaluate((element) => ({ position: getComputedStyle(element).position, border: getComputedStyle(element).borderBottomWidth, background: getComputedStyle(element).backgroundColor })))
    .toEqual({ position: "absolute", border: "0px", background: "rgba(0, 0, 0, 0)" });
  await expect(sheet(page).getByRole("heading", { name: "계획 확인" })).toHaveCount(1);                 // 제목은 화면 읽기용으로 남는다
  await expect(sheet(page).getByRole("heading", { name: "계획 확인" })).toHaveClass(/sr-only/);
  // 칩은 여전히 동작한다
  await page.getByRole("tab", { name: /^2일차/ }).click();
  await expect(page.getByRole("tab", { name: /^2일차/ })).toHaveAttribute("aria-selected", "true");
  await expect(card(page, "N서울타워")).toBeVisible();
});

test("확인이 끝나면 목록은 맨 위(첫날의 첫 일정)에서 시작한다 — 읽는 중에 따라가던 자리(첫날 중간)에 남지 않는다", async ({ page, request }) => {
  // 읽는 동안 그려지는 장면을 지나온 접수(readingPolls 3): 목록은 그려지는 줄을 따라 내려갔다가 끝나면 맨 위로 돌아와야 한다.
  const server = mockServer(request);
  // This exercises the polling path: the mock server's one-shot SSE snapshot cannot advance readingPolls.
  await server.scenario({ review: "on", board: "rich", readingPolls: 3, intakeEvents: "off" });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill("10/1 09:00 경복궁 관람");
  await checkPlan(page);
  await expect(needsBadge(page)).toBeVisible({ timeout: 40_000 });
  await page.waitForTimeout(2500);                                                                      // 맨 위로 돌아오는 움직임이 끝나도록
  const top = await page.locator('[class*="sheetBody"]').first().evaluate((element) => element.scrollTop);
  expect(top).toBeLessThan(4);
  await expect(card(page, "경복궁 관람")).toBeInViewport();
});

test("카드 도구가 좁은 카드에서 제목을 한 글자로 누르지 않고 제목 폭과 높이를 유지한다", async ({ page, request }) => {
  await openFinished(page, request);
  const title = card(page, "올리브영").getByRole("heading").getByRole("button");
  const box = (await title.boundingBox())!;
  expect(box.width).toBeGreaterThan(110);                                                                // 제목 칸이 9em 이상을 지킨다
  expect(box.height).toBeLessThan(60);                                                                   // 세로로 꺾이지 않았다
});

test("이름 수정 버튼은 펼쳐졌을 때 칩 오른쪽 끝에 붙지 않고 여백이 있다", async ({ page, request }) => {
  await openFinished(page, request);
  await page.getByRole("button", { name: /^계획 이름 · / }).click();
  const edit = page.getByRole("button", { name: /^계획 이름 바꾸기/ });
  await expect(edit).toBeVisible();
  const chip = page.locator('[class*="headInfo"]').first();
  const [chipBox, editBox] = [await chip.boundingBox(), await edit.boundingBox()];
  expect((chipBox!.x + chipBox!.width) - (editBox!.x + editBox!.width)).toBeGreaterThanOrEqual(8);       // 오른쪽에 8px 이상 여백
});

test("이동 수단 범례는 없고 선은 수단별 색으로 그려진다", async ({ page, request }) => {
  await openFinished(page, request, undefined, { intakeRoutes: "on" });
  await expect(page.locator("[data-route-tags]")).toHaveCount(0);
  const colors = await page.evaluate(() => {
    const css = (variable: string) => getComputedStyle(document.documentElement).getPropertyValue(variable).trim().toLowerCase();
    return { subway: css("--color-adjusted"), walk: css("--color-muted"), lines: Array.from(document.querySelectorAll("path.trip-route-line")).map((path) => (path.getAttribute("stroke") ?? "").toLowerCase()) };
  });
  expect(colors.lines).toContain(colors.subway);
  expect(colors.lines).toContain(colors.walk);
});

test("지하철 선을 누르면 탄 구간(호선 · 역)이 설명 알림에 더해진다 — 서버가 준 것만, 중간 역을 못 채웠으면 「역 사이는 직선」", async ({ page, request }) => {
  await page.route("**/v1/web/trip-intakes/**/route-shapes*", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.shapes[0].rides = [
      { line: "지하철 3호선", from: "경복궁", to: "을지로3가", stations: ["경복궁", "안국", "충무로", "을지로3가"], count: 4, filled: true },
      { line: "지하철 1호선", from: "을지로3가", to: "종각", stations: [], count: 1, filled: false },
    ];
    await route.fulfill({ response, json: body });
  });
  await openFinished(page, request, undefined, { intakeRoutes: "on" });
  await page.locator("path.trip-route-hit").first().dispatchEvent("click");
  const note = callout(page, /^→경복궁 관람 → 올리브영/);
  await expect(note).toContainText("지하철 3호선 · 경복궁→을지로3가 · 4개 역");
  await expect(note).toContainText("지하철 1호선 · 을지로3가→종각 · 1개 역 · 역 사이는 직선");
});
