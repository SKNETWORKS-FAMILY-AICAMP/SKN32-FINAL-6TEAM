import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { mockServer, noHorizontalScroll, start } from "./helpers";

/**
 * 계획 확인 화면(`/intakes/[id]`)의 「화면 자체」 동작 — 서버가 무엇을 답하느냐보다 화면이 어떻게 움직이느냐를 지키는 시험.
 * 테스트용 모방 서버로 도는 자동 시험이다(실제 서버 아님).
 *
 * ★`[2026-10-03]` 예시 데이터로 도는 미리보기 화면(`/preview/plan-check`)을 없애면서, 그 화면을 보던 `tests/e2e/plan-check.spec.ts` 의
 *   18개 중 실제 화면에서도 뜻이 있는 것만 여기로 옮겼다. 서버와 이어진 부분(잠금·삭제 되돌리기·후보 바꾸기·검색/사진·전체 자동 추천 →
 *   재검증 → 등록·목록 끝 밀기·읽는 동안 내용 채움)은 `server-review.spec.ts` · `flow.spec.ts` · `progress.spec.ts` 가 이미 서버 연결로 본다.
 *
 * 장면: 모방 서버의 `review: "on"` + `board: "rich"` — 장소 셋(경복궁 관람 · 올리브영(확인 필요) · 광장시장)과 이동 둘(지하철 3호선 · 1호선).
 * 모방 서버의 판은 하루뿐이고 올리브영에도 좌표가 있어서, 「일차 머리」와 「위치 미정」을 보려면 서버 응답을 `patchIntake` 로 바꿔 쓴다(서버가 그렇게
 * 답한 것처럼 — 화면 코드는 그대로다).
 */
const INTAKE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const INTAKE_READ = `**/v1/web/trip-intakes/${INTAKE}`;
const SUMMARY = "장소 1곳 · 이동 1구간 확인 필요";

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- 서버 응답을 시험에서 고쳐 쓰는 자리라 모양을 고정하지 않는다
type Json = Record<string, any>;

const card = (page: Page, title: string) => page.getByRole("article", { name: title, exact: true });
/** 카드 머리의 제목 단추(펼침·접힘). */
const head = (page: Page, title: string) => card(page, title).getByRole("heading").getByRole("button");
/**
 * 지도의 핀 — Leaflet 이 만든 `role=button` 요소이고 `title` 이 「1. 경복궁 관람 · 2026-10-01 09:00」 꼴(번호. 제목 · 날짜 시각)이다.
 * 접근성 이름은 핀 안의 글자(「1」)가 이기므로 이름이 아니라 title 의 앞부분으로 찾는다. `aria-pressed` 는 이 바깥 요소에 붙는다.
 */
// 지도가 움직이는 동안 Playwright 의 「안정됨」 확인이 끝나지 않아 .click() 이 밀리므로, 핀은 click 이벤트를 직접 보낸다(Leaflet 이 그 이벤트를 듣는다).
const pin = (page: Page, label: string) => page.locator(`.leaflet-marker-icon[title^="${label}"]`);
const sheet = (page: Page) => page.getByRole("region", { name: /장소·운영시간 확인|계획 확인|등록 완료/ });
const toast = (page: Page, text: string) => page.getByRole("status").filter({ hasText: text });

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

/** 접수 조회(GET)의 모방 서버 응답을 `change` 로 고쳐서 돌려 준다 — 쓰기 요청은 그대로 통과. 화면을 열기 전에 건다. */
async function patchIntake(page: Page, change: (view: Json) => void) {
  await page.route(INTAKE_READ, async (route) => {
    if (route.request().method() !== "GET") { await route.continue(); return; }
    const response = await route.fetch();
    const view = await response.json();
    change(view);
    await route.fulfill({ response, json: view });
  });
}

/** 하루 뒤 일정 하나 — 모방 서버의 판에는 없는 둘째 날이다. */
const DAY_TWO_STOP: Json = {
  id: "0-3", source_id: "s1", index: 3, title: "N서울타워", kind: "activity", day: 2, date: "2026-10-02", starts_at: "10:00", ends_at: "11:30",
  locked: false, status: "keep", can_lock: true, place_state: "found", candidates_hint: null,
  place: { name: "N서울타워", latitude: 37.5512, longitude: 126.9882, source: "tour_api", kind: null, content_id: null, content_type_id: null },
  rows: [{ row: "place", result: "ok", text: "관광공사 정보로 찾았어요" }],
};

/** 이미 읽힌 접수를 바로 연다(읽는 중 화면을 건너뛴다). `patch` 가 있으면 서버 응답을 그렇게 고친 채로. */
async function openFinished(page: Page, request: APIRequestContext, patch?: (view: Json) => void) {
  const server = mockServer(request);
  await server.scenario({ review: "on", board: "rich", readingPolls: 0 });
  if (patch) await patchIntake(page, patch);
  await start(page);
  await page.goto(`/intakes/${INTAKE}`);
  await expect(page.getByText(SUMMARY, { exact: true })).toBeVisible();
  return server;
}

/** 서버가 아직 읽는 중인 접수를 연다 — 모방 서버의 실시간 진행을 꺼서(404) 1.5초 조회로만 따라가게 하고, 99번 조회할 때까지 「읽는 중」이다. */
async function openReading(page: Page, request: APIRequestContext) {
  await mockServer(request).scenario({ readingPolls: 99, intakeEvents: "off" });
  await start(page);
  await page.goto(`/intakes/${INTAKE}`);
  await expect(page.getByRole("heading", { name: "계획을 확인하고 있어요", level: 1 })).toBeVisible();
}

// ── 읽는 중 ──────────────────────────────────────────────────────────────────

test("「움직임 줄이기」 설정이면 읽는 중에서 결과로 넘어갈 때 다시 그리지 않고 서버 결과를 바로 보인다", async ({ page, request }) => {
  await mockServer(request).scenario({ review: "on", board: "rich", intakeEvents: "on", readingPolls: 1 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await start(page);
  await page.goto(`/intakes/${INTAKE}`);
  // 천천히 다시 그리면 이 판(장소 셋 · 이동 둘 · 검사 줄)을 다 그리는 데 7~8초가 든다(`use-reveal.ts` 의 REVEAL_BUDGET_MS = 8초). 바로 그리면 한두 초 안에 끝난다.
  await expect(page.getByRole("heading", { name: "내 여행", level: 1 })).toBeVisible({ timeout: 5_000 });
  await expect(page.getByText(SUMMARY, { exact: true })).toBeVisible({ timeout: 5_000 });
});

test("읽는 중 화면의 뒤로 화살표는 계획 입력 화면으로 돌아간다", async ({ page, request }) => {
  await openReading(page, request);
  await page.getByRole("button", { name: "뒤로", exact: true }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
});

// ── 화면 폭 ──────────────────────────────────────────────────────────────────

const WIDTHS = [[1280, 900], [375, 812], [320, 640]];

test("PC 기기 틀·375px·320px에서 읽는 중 화면이 가로로 넘치지 않는다(긴 원문 줄이 있어도)", async ({ page, request }) => {
  // 모방 서버가 주는 줄은 짧은 하나뿐이라, 실제 계획 글처럼 긴 줄 셋으로 바꿔 읽게 한다
  await patchIntake(page, (view) => {
    view.sources[0].lines = [
      { no: 1, text: "10월 1일 서울 여행 — 부모님과 둘이 가는 당일치기 코스", read: false },
      { no: 2, text: "09:00 경복궁 관람을 마치고 북촌 한옥마을까지 천천히 걸어서 이동한 뒤 근처 한식당에서 점심 먹기 (비가 오면 박물관으로)", read: false },
      { no: 3, text: "15:00 쇼핑 — 올리브영에서 화장품을 사고 광장시장에서 빈대떡과 마약김밥을 먹은 다음 청계천을 따라 걸어서 숙소로 돌아오기", read: false },
    ];
  });
  await openReading(page, request);
  for (const [width, height] of WIDTHS) {
    await page.setViewportSize({ width, height });
    await page.goto(`/intakes/${INTAKE}`);
    await expect(page.getByText("찾은 일정")).toBeVisible();
    await expect(page.getByText("15:00 쇼핑 — 올리브영에서")).toBeVisible();
    await noHorizontalScroll(page);
  }
});

test("PC 기기 틀·375px·320px에서 결과 화면과 바꾸기 화면이 가로로 넘치지 않는다", async ({ page, request }) => {
  test.setTimeout(90_000);
  await mockServer(request).scenario({ review: "on", board: "rich", readingPolls: 0 });
  await start(page);
  for (const [width, height] of WIDTHS) {
    await page.setViewportSize({ width, height });
    await page.goto(`/intakes/${INTAKE}`);
    await expect(page.getByText(SUMMARY, { exact: true })).toBeVisible();
    await noHorizontalScroll(page);
    await card(page, "올리브영").scrollIntoViewIfNeeded();
    await expect(card(page, "올리브영")).toBeInViewport({ ratio: 0.5 });
    await page.getByRole("button", { name: "올리브영 수정" }).click();
    await expect(page.getByRole("heading", { name: "올리브영 바꾸기" })).toBeVisible();
    await noHorizontalScroll(page);                                     // 후보 카드는 자기 줄 안에서 옆으로 넘긴다
  }
});

// ── 결과: 카드 · 핀 · 일차 · 시트 · 이동 줄 ───────────────────────────────────────

test("결과: 카드는 하나씩 펼쳐지고, 카드를 고르면 지도의 그 핀이 선택되며, 핀을 누르면 그 카드가 펼쳐진다", async ({ page, request }) => {
  await openFinished(page, request);
  await expect(head(page, "경복궁 관람")).toHaveAttribute("aria-expanded", "false");
  await head(page, "경복궁 관람").click();
  await expect(head(page, "경복궁 관람")).toHaveAttribute("aria-expanded", "true");
  await expect(card(page, "경복궁 관람").getByText("관광공사 정보로 찾았어요")).toBeVisible();
  await head(page, "광장시장").click();
  await expect(head(page, "광장시장")).toHaveAttribute("aria-expanded", "true");
  await expect(head(page, "경복궁 관람")).toHaveAttribute("aria-expanded", "false");              // 한 번에 카드 하나
  await expect(pin(page, "3. 광장시장")).toHaveAttribute("aria-pressed", "true");
  await pin(page, "1. 경복궁 관람").dispatchEvent("click");                                                       // 핀이 그 카드를 연다
  await expect(head(page, "경복궁 관람")).toHaveAttribute("aria-expanded", "true");
  await expect(pin(page, "1. 경복궁 관람")).toHaveAttribute("aria-pressed", "true");
});

test("결과: 일차 머리를 누르면 지도가 그 날로 바뀐다", async ({ page, request }) => {
  await openFinished(page, request, (view) => { view.review.items.push(DAY_TWO_STOP); });
  const day2 = page.getByRole("button", { name: /^2일차/ });
  await expect(pin(page, "1. 경복궁 관람")).toBeVisible();
  await expect(day2).toHaveAttribute("aria-pressed", "false");
  await day2.click();
  await expect(day2).toHaveAttribute("aria-pressed", "true");
  await expect(pin(page, "1. N서울타워")).toBeVisible();
  await expect(pin(page, "1. 경복궁 관람")).toHaveCount(0);
  await page.getByRole("button", { name: /^1일차/ }).click();                                      // 첫날로 돌아오면 첫날 핀이 다시 그려진다
  await expect(pin(page, "1. 경복궁 관람")).toBeVisible();
  await expect(pin(page, "1. N서울타워")).toHaveCount(0);
});

test("결과: 손잡이는 시트를 높게·낮게·중간으로 돌린다", async ({ page, request }) => {
  await openFinished(page, request);
  const screen = page.locator("[data-sheet]");
  const handle = page.getByRole("button", { name: "목록 높이 바꾸기" });
  await expect(screen).toHaveAttribute("data-sheet", "half");
  await handle.click();
  await expect(screen).toHaveAttribute("data-sheet", "full");
  await handle.click();
  await expect(screen).toHaveAttribute("data-sheet", "peek");
  await handle.click();
  await expect(screen).toHaveAttribute("data-sheet", "half");
});

test("결과: 목록 높이는 손잡이를 잡고 끌면 원하는 높이로 맞춰지고, 위·아래 화살표로도 바뀌며, 누르면 다시 눈금으로 돌아간다", async ({ page, request }) => {
  await openFinished(page, request);
  const screen = page.locator("[data-sheet]");
  const handle = page.getByRole("button", { name: "목록 높이 바꾸기" });
  const height = () => sheet(page).evaluate((element) => Math.round(element.getBoundingClientRect().height));
  await expect(screen).toHaveAttribute("data-sheet", "half");
  await expect.poll(height).toBeGreaterThan(300);
  const start0 = await height();
  const box = (await handle.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + 10);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2, box.y - 80, { steps: 6 });
  await page.mouse.up();
  await expect(screen).toHaveAttribute("data-sheet", "custom");
  await expect.poll(height).toBeGreaterThanOrEqual(start0 + 70);
  const dragged = await height();
  await handle.focus();
  await page.keyboard.press("ArrowDown");
  await expect.poll(height).toBeLessThan(dragged - 30);
  await handle.click();                                                     // 끌고 난 뒤의 누름은 눈금(중간)으로 돌아간다
  await expect(screen).toHaveAttribute("data-sheet", "half");
});

test("결과: 이동 줄을 누르면 경로·수단·도착 검사가 펼쳐진다", async ({ page, request }) => {
  await openFinished(page, request);
  const move = page.getByRole("button", { name: /지하철 3호선.*9분 · 0\.6km/ });
  await expect(move).toHaveAttribute("aria-expanded", "false");
  await move.click();
  await expect(move).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByText("올리브영 인사동점을 임시로 골라서 계산했어요")).toBeVisible();
  await expect(page.getByText("일정보다 39분 늦어요")).toBeVisible();
});

test("결과: 좌표가 없는 장소는 핀 없이 지도 위에 「위치 미정」으로 알리고, 나머지 핀의 번호는 그대로다", async ({ page, request }) => {
  await openFinished(page, request, (view) => {
    const olive = view.review.items[1];
    olive.place = { ...olive.place, latitude: null, longitude: null };
  });
  await expect(page.getByText("위치 미정 · 올리브영")).toBeVisible();
  await expect(pin(page, "1. 경복궁 관람")).toBeVisible();
  await expect(pin(page, "3. 광장시장")).toBeVisible();
  await expect(pin(page, "2. 올리브영")).toHaveCount(0);
});

// ── 카드 도구 ────────────────────────────────────────────────────────────────

test("카드의 「자동 추천」은 시간이 맞는 첫 후보로 바꾸고, 바꾼 장소를 좌표째 서버로 보낸다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await head(page, "올리브영").click();
  await card(page, "올리브영").getByRole("button", { name: "자동 추천" }).click();
  await expect(toast(page, "대체 후보 1순위로 바꿨어요")).toBeVisible();
  const [edit] = await server.received("POST", "/edits");
  expect(edit.body).toEqual({ revision: 1, edits: [{ source_id: "s1", field: "items[1].place",
    value: { name: "올리브영 광화문점", latitude: 37.5717, longitude: 126.9791, source: "kakao" } }] });
  await expect(card(page, "올리브영 광화문점")).toBeVisible();
});

test("삭제 확인창: Tab은 두 단추 안에서만 돌고, 바깥을 누르면 닫히며, 320px에서도 화면 안에 있다", async ({ page, request }) => {
  await page.setViewportSize({ width: 320, height: 640 });
  const server = await openFinished(page, request);
  await page.getByRole("button", { name: "올리브영 삭제" }).click();
  const dialog = page.getByRole("alertdialog", { name: "올리브영 일정을 삭제하시겠습니까?" });
  await expect(dialog).toBeInViewport();
  await expect(dialog).toContainText("삭제한 뒤 잠시 「되돌리기」로 되돌릴 수 있습니다.");
  await noHorizontalScroll(page);
  await expect(dialog.getByRole("button", { name: "취소" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(dialog.getByRole("button", { name: "삭제" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(dialog.getByRole("button", { name: "취소" })).toBeFocused();
  await page.mouse.click(5, 300);
  await expect(dialog).toHaveCount(0);
  expect(await server.received("POST", "/edits")).toHaveLength(0);                 // 묻기만 했다: 서버로는 아무것도 가지 않았다
});

// ── 수정(바꾸기) 화면 ────────────────────────────────────────────────────────

test("수정 화면: 지금 일정과 후보 A·B를 넘기면 지도의 핀이 따라가고, 핀을 누르면 그 카드로 간다", async ({ page, request }) => {
  await openFinished(page, request);
  await page.getByRole("button", { name: "올리브영 수정" }).click();
  await expect(page.getByRole("heading", { name: "올리브영 바꾸기" })).toBeVisible();
  await expect(page.getByText("지금 일정 · 1/3")).toBeVisible();                              // 지금 일정 + 서버가 준 후보 둘
  await expect(page.getByText("옆으로 넘기면 다른 후보 2곳 →")).toBeVisible();
  await expect(pin(page, "A. 올리브영 광화문점")).toBeVisible();                               // 후보는 A · B · C 글자 핀
  await expect(pin(page, "B. 올리브영 종각점")).toBeVisible();
  await expect(pin(page, "2. 올리브영")).toHaveAttribute("aria-pressed", "true");             // 바꾸는 일정의 핀이 선택돼 있다

  await page.getByRole("button", { name: "후보 A", exact: true }).click();                    // 점을 누르면 카드와 핀이 함께 간다
  await expect(page.getByText("대체 후보 A · 2/3")).toBeVisible();
  await expect(pin(page, "A. 올리브영 광화문점")).toHaveAttribute("aria-pressed", "true");
  await expect(pin(page, "2. 올리브영")).toHaveAttribute("aria-pressed", "false");
  await pin(page, "B. 올리브영 종각점").dispatchEvent("click");                                               // 핀을 누르면 그 카드가 온다
  await expect(page.getByText("대체 후보 B · 3/3")).toBeVisible();
  await expect(pin(page, "B. 올리브영 종각점")).toHaveAttribute("aria-pressed", "true");

  await page.getByRole("button", { name: /시트를 위로 올리면/ }).click();                     // 사진 안내 단추는 시트를 높게 올린다
  await expect(page.locator("[data-sheet]")).toHaveAttribute("data-sheet", "full");
});

test("수정 화면의 「직접 고치기」: 끝이 시작보다 빠르거나 장소가 비면 보내지 않고, 「바꾸기 그만두기」는 수정 단추로 돌아간다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await page.getByRole("button", { name: "광장시장 수정" }).click();
  await page.getByText("직접 고치기 · 이름·날짜·시각·장소 없음").click();
  const editor = page.getByRole("form", { name: "「광장시장」 고치기" });
  await editor.getByLabel("끝").fill("12:00");                                                  // 광장시장은 12:30 시작
  await editor.getByRole("button", { name: "저장" }).click();
  await expect(editor.getByRole("alert")).toHaveText("끝 시각이 시작보다 빨라요.");
  await editor.getByLabel("끝").fill("13:30");
  await editor.getByRole("searchbox", { name: "장소 이름" }).fill("");
  await editor.getByRole("button", { name: "저장" }).click();
  await expect(editor.getByRole("alert")).toHaveText("장소 이름을 적거나 「장소 없음」을 골라 주세요.");
  expect(await server.received("POST", "/edits")).toHaveLength(0);                          // 화면이 먼저 막았다: 서버로는 아무것도 가지 않았다
  await editor.getByRole("button", { name: "취소" }).click();
  await expect(editor).toHaveCount(0);
  await page.getByRole("button", { name: "바꾸기 그만두기" }).click();
  await expect(page.getByRole("heading", { name: "광장시장 바꾸기" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "광장시장 수정" })).toBeFocused();
});

test("수정 화면: 장소 검색은 로고 자리(머리줄)에 작게 들어 있고, 눌러서 쓰는 동안 넓어진다 — 따로 막대를 차지하지 않는다", async ({ page, request }) => {
  await openFinished(page, request);
  await page.getByRole("button", { name: "올리브영 수정" }).click();
  const search = page.getByRole("searchbox", { name: "장소 검색" });
  const field = page.locator("[class*=headSearch]");
  await expect(page.locator("header").filter({ has: search })).toHaveCount(1);
  await expect(page.getByRole("link", { name: /triPilot — 소개 화면/ })).toBeHidden();          // 검색이 로고 자리를 쓴다
  await expect(page.getByRole("button", { name: "메뉴", exact: true })).toBeVisible();
  const compact = (await field.boundingBox())!;
  await search.click();
  await expect.poll(async () => (await field.boundingBox())!.width).toBeGreaterThan(compact.width + 40);
  await search.fill("명동");
  await expect(page.getByText("‘명동’ 검색 결과 1곳")).toBeVisible();
  await page.getByRole("button", { name: "바꾸기 그만두기" }).click();
  await expect(page.getByRole("link", { name: /triPilot — 소개 화면/ })).toBeVisible();          // 수정이 끝나면 로고가 돌아온다
});

test("「직접 고치기」에서 「장소 없음」으로 저장하면 서버에 `place {none: true}` 가 가고, 카드가 「조정」이 되고 위치 미정으로 보인다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await page.getByRole("button", { name: "경복궁 관람 수정" }).click();
  await page.getByText("직접 고치기 · 이름·날짜·시각·장소 없음").click();
  const editor = page.getByRole("form", { name: "「경복궁 관람」 고치기" });
  await editor.getByLabel("장소 없음(자유 시간 등)").check();
  await editor.getByRole("button", { name: "저장" }).click();
  await expect(toast(page, "저장했어요.")).toBeVisible();
  const [edit] = await server.received("POST", "/edits");
  expect(JSON.stringify(edit.body)).toContain('"none":true');
  await expect(card(page, "경복궁 관람").getByText("조정")).toBeVisible();
  await expect(page.getByText(/위치 미정 · .*경복궁 관람/)).toBeVisible();
});
