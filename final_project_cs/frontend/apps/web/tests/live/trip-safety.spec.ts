import { expect, test, type Page } from "@playwright/test";
import { mockServer, start, TRIP_ID } from "./helpers";

/**
 * `[2026-10-06 사용자 결정 — 재난 시 일정 정지 + 대피 안내]` 여행 화면: 정지 중 표시 · 정지된 일정 표시 · 안전 알림의 안내(대피 장소 · 119) · 「일정 다시 시작」. mock 서버 시험이다 — 화면 반응만 본다.
 * mock 서버에 이 응답이 아직 없어서 여행 조회 · 알림 조회 · 다시 시작을 시험 안에서 바꿔 끼운다(`page.route`). ★서버가 실제로 이 모양을 내는지(로컬 개발 DB 시험은 cs 개발 세션이 했다)와
 * 실제 재난문자는 못 봤다 — 계약 정본은 `wiki/external/rest-endpoints.md` 「재난 시 일정 정지」.
 */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const PAUSE = {
  paused: true, level: "day", label: "지진 — 오늘 남은 일정 정지", since: "2026-10-06T05:05:00Z", until: "2026-10-06T15:00:00Z", day: "2026-10-06", released: false,
  resume: { label: "일정 다시 시작", path: "/safety/resume" },
};
const ALERT = {
  key: "n-safety-1", type: "safety_alert", kind: "safety_pause_day", at: "2026-10-06T05:06:00Z", delivery: "sent", version: null, proposal_id: null,
  text: "⚠️ 안전 알림 — 지진. 오늘 남은 일정을 정지했어요.\n공식 안내(국민재난안전포털)를 먼저 따르고, 위급하면 119에 전화하세요.",
  safety: {
    level: "day", label: "지진", official: { source: "행정안전부", text: "안전한 곳으로 대피하세요", at: "2026-10-06T05:05:00Z" }, emergency_call: "119", portal: "국민재난안전포털",
    reference: { place: "경복궁", latitude: 37.5796, longitude: 126.977, note: "일정에 적힌 장소 기준이에요. 지금 계신 곳과 다를 수 있어요." },
    shelters: [{ name: "경복궁 옥외대피장소", address: "서울 종로구 사직로 161", distance_m: 320, walk_minutes_estimate: 5, underground: false, capacity: 1200, map_url: "https://www.google.com/maps/dir/?api=1&destination=37.58,126.97&travelmode=walking" }],
    shelter_status: "ok",
  },
};

/** 여행 조회 · 알림 조회 · 다시 시작을 `state` 대로 바꿔 끼운다. 다시 시작을 누르면 `state.paused` 가 꺼진다. */
async function stage(page: Page, state: { paused: boolean; safety?: Record<string, unknown>; alert?: boolean; resumeFails?: boolean; resumed: number }) {
  await page.route(`**/v1/web/trips/${TRIP_ID}`, async (route) => {
    if (route.request().method() !== "GET") { await route.continue(); return; }
    const response = await route.fetch();
    const trip = await response.json();
    trip.safety = state.paused ? (state.safety ?? PAUSE) : { paused: false };
    trip.items = (trip.items as { paused?: boolean }[]).map((item, index) => ({ ...item, paused: state.paused && index < 2 }));
    await route.fulfill({ response, json: trip });
  });
  await page.route(`**/v1/web/trips/${TRIP_ID}/notices`, async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.notices = [...(body.notices ?? []), ...(state.paused && state.alert !== false ? [ALERT] : [])];
    await route.fulfill({ response, json: body });
  });
  await page.route(`**/v1/web/trips/${TRIP_ID}/safety/resume`, async (route) => {
    state.resumed += 1;
    if (state.resumeFails) { await route.fulfill({ status: 500, json: { error: { code: "internal_error", message: "다시 시작하지 못했어요. 잠시 뒤 다시 눌러 주세요." } } }); return; }
    state.paused = false;
    await route.fulfill({ json: { resumed: 1, safety: { paused: false } } });
  });
}
async function openTrip(page: Page) {
  await start(page);
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(page.getByRole("heading", { name: "나의 여행", exact: true })).toBeVisible();
}
const panel = (page: Page) => page.getByTestId("safety-panel");

test("정지 중이면 맨 위에 「일정 정지 중」과 이유 · 시각 · 안전 안내(119 · 대피 장소 · 기준점 안내)가 서고, 정지된 일정에는 「일정 정지」 표시가 붙는다", async ({ page }) => {
  await stage(page, { paused: true, resumed: 0 });
  await openTrip(page);
  await expect(panel(page)).toBeVisible();
  await expect(panel(page).getByRole("heading", { name: "일정 정지 중" })).toBeVisible();
  await expect(panel(page)).toContainText("지진 — 오늘 남은 일정 정지");                                  // 서버의 말
  await expect(panel(page)).toContainText("2026-10-06 14:05부터");                                         // 한국 시각
  await expect(panel(page)).toContainText("2026-10-07 00:00까지");
  await expect(panel(page)).toContainText("공식 안내(국민재난안전포털)를 먼저 따르고");                       // 알림 글 그대로
  await expect(panel(page).getByRole("link", { name: "119에 전화" })).toHaveAttribute("href", "tel:119");
  await expect(panel(page).getByText("경복궁 옥외대피장소")).toBeVisible();
  await expect(panel(page)).toContainText("직선 320m · 걸어서 약 5분(추정)");                                // 걷는 시간은 추정이라고 밝힌다
  await expect(panel(page).getByRole("link", { name: "걸어서 길 찾기" })).toHaveAttribute("href", /^https:\/\/www\.google\.com\/maps\//);
  await expect(panel(page)).toContainText("지금 계신 곳과 다를 수 있어요");                                  // 기준점은 일정 장소다
  await expect(page.getByText("일정 정지", { exact: true })).toHaveCount(2);                              // 일정 둘이 정지됨
  const [safety, plan] = [await panel(page).boundingBox(), await page.getByRole("heading", { name: "나의 여행" }).boundingBox()];
  expect(safety!.y).toBeGreaterThan(plan!.y);                                                              // 제목 아래, 다른 안내보다 위
});

test("안전 안내가 다시 시작 단추보다 먼저 나오고, 단추 옆에 「안전한 곳에서 눌러 주세요」가 있으며, 자동으로 다시 시작되지 않는다", async ({ page }) => {
  const state = { paused: true, resumed: 0 };
  await stage(page, state);
  await openTrip(page);
  const guidanceAt = await panel(page).getByText("가까운 대피 장소").boundingBox();
  const resume = panel(page).getByRole("button", { name: "일정 다시 시작" });
  await expect(resume).toBeVisible();
  expect(guidanceAt!.y).toBeLessThan((await resume.boundingBox())!.y);
  await expect(resume).toHaveAccessibleDescription("안전한 곳에 계신 것을 확인한 뒤에 눌러 주세요.");
  await page.waitForTimeout(1500);
  expect(state.resumed).toBe(0);                                                                           // 누르기 전에는 서버를 부르지 않는다
});

test("「일정 다시 시작」을 누르면 서버에 한 번 알리고 정지 표시와 일정의 「일정 정지」 표시가 사라진다", async ({ page }) => {
  const state = { paused: true, resumed: 0 };
  await stage(page, state);
  await openTrip(page);
  await panel(page).getByRole("button", { name: "일정 다시 시작" }).click();
  await expect(panel(page)).toHaveCount(0);
  await expect(page.getByText("일정 정지", { exact: true })).toHaveCount(0);
  expect(state.resumed).toBe(1);
});

test("다시 시작하지 못하면 이유를 알리고 정지는 그대로 둔다 (다시 누를 수 있다)", async ({ page }) => {
  const state = { paused: true, resumed: 0, resumeFails: true };
  await stage(page, state);
  await openTrip(page);
  await panel(page).getByRole("button", { name: "일정 다시 시작" }).click();
  await expect(panel(page).getByRole("alert")).toContainText("다시 시작하지 못했어요");
  await expect(panel(page)).toBeVisible();
  await expect(panel(page).getByRole("button", { name: "일정 다시 시작" })).toBeEnabled();
});

test("여행 전체 정지는 「다시 시작할 때까지 멈춰 있어요」, 대피 장소 자료가 없으면(안내만) 목록 없이 서버의 글만 보인다", async ({ page }) => {
  await stage(page, { paused: true, resumed: 0, safety: { ...PAUSE, level: "trip", until: null, label: "전쟁 — 여행 전체 정지" } });
  await page.route(`**/v1/web/trips/${TRIP_ID}/notices`, async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    // 서버가 대피 장소 자료 표가 빈 채로 보내는 알림: 글 끝에 「가까운 대피 장소 자료를 아직 불러오지 못했어요…」가 붙고 목록은 비어 있다(2026-10-06 서버 `safety_pause.py`)
    const text = `${ALERT.text}
가까운 대피 장소 자료를 아직 불러오지 못했어요. 재난문자와 공식 안내를 따라 주세요.`;
    body.notices = [...(body.notices ?? []), { ...ALERT, text, safety: { ...ALERT.safety, shelters: [], shelter_status: "no_data" } }];
    await route.fulfill({ response, json: body });
  });
  await openTrip(page);
  await expect(panel(page)).toContainText("전쟁 — 여행 전체 정지");
  await expect(panel(page)).toContainText("다시 시작할 때까지 멈춰 있어요");
  await expect(panel(page).getByRole("heading", { name: "가까운 대피 장소" })).toHaveCount(0);               // 없는 대피 장소를 만들지 않는다
  await expect(panel(page)).toContainText("가까운 대피 장소 자료를 아직 불러오지 못했어요. 재난문자와 공식 안내를 따라 주세요.");   // 서버가 말한 이유는 그대로 보인다
  await expect(panel(page)).toContainText("공식 안내(국민재난안전포털)를 먼저 따르고");
  await expect(panel(page).getByRole("link", { name: "119에 전화" })).toBeVisible();
});

test("아직 시작하지 않은 여행의 정지: 「현지 상황을 몰라 멈췄어요」로 말하고 대피 장소는 아예 숨기며, 다시 시작 안내가 다르다", async ({ page }) => {
  await stage(page, { paused: true, resumed: 0, safety: { ...PAUSE, level: "trip", phase: "upcoming", until: null, label: "전쟁 — 여행 전체 정지" } });
  await page.route(`**/v1/web/trips/${TRIP_ID}/notices`, async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.notices = [...(body.notices ?? []), { ...ALERT, text: "가기 전에 공식 안내(국민재난안전포털)로 현지 상황을 확인하세요. 위급하면 119.", safety: { ...ALERT.safety, phase: "upcoming", shelters: [], shelter_status: "not_applicable" } }];
    await route.fulfill({ response, json: body });
  });
  await openTrip(page);
  await expect(panel(page)).toHaveAttribute("data-phase", "upcoming");
  await expect(panel(page)).toContainText("아직 시작하지 않은 여행이지만 현지 상황을 몰라 멈췄어요");
  await expect(panel(page)).toContainText("다시 시작할 때까지 멈춰 있어요");                                  // 시작일이 와도 사용자가 풀 때까지
  await expect(panel(page)).toContainText("가기 전에 공식 안내(국민재난안전포털)로 현지 상황을 확인하세요");     // 서버의 글
  await expect(panel(page).getByText("가까운 대피 장소")).toHaveCount(0);                                    // 대피 장소 카드는 비어 있다고 그리지 않고 숨긴다
  await expect(panel(page).getByRole("button", { name: "일정 다시 시작" })).toHaveAccessibleDescription("가기 전에 현지 상황을 확인한 뒤에 눌러 주세요.");
});

test("정지가 없는 여행(또는 이 값을 모르는 옛 서버)에는 아무것도 안 보인다", async ({ page }) => {
  await stage(page, { paused: false, resumed: 0 });
  await openTrip(page);
  await expect(panel(page)).toHaveCount(0);
  await expect(page.getByText("일정 정지", { exact: true })).toHaveCount(0);
});
