import { expect, test, type Page } from "@playwright/test";
import { mockServer, openNotices, start, TRIP_ID, tripScreen } from "./helpers";

/**
 * `[2026-10-06 사용자 결정 — 재난 뒤 다시 시작]` 여행 화면: 다시 시작한 직후 상황 꾸러미(아는 것 · 모르는 것 · 남은 일정의 영향 · 세 가지 길 · 「오늘은 가볍게」 · 질문 둘). 우리가 대신 정하지 않는다 —
 * 아무것도 미리 골라 두지 않고, 모르면 「범위 모름」(「영향 없음」이 아니다), 못 하는 것(예약 · 연기 · 취소)은 서버 문장 그대로. 테스트용 mock 서버로 도는 자동 시험이다(화면 반응 — 실서버 확인 아님).
 * mock 서버에 이 응답이 아직 없어서 시험 안에서 바꿔 끼운다(`page.route`). 계약: `wiki/external/rest-endpoints.md` 「재난 뒤 다시 시작」.
 */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const BRIEF = {
  pause_id: "pause-1", phase: "in_progress", level: "day", resumed_at: "2026-10-06T10:00:00+00:00",
  event: { label: "호우", kind: "disaster", category: "disaster_msg", at: "2026-10-06T05:05:00Z", official_text: "종로구 호우 대피 안내" },
  facts: ["행정안전부 긴급재난문자: 종로구 호우 대피 안내", "사건 시각: 2026-10-06T05:05:00Z"],
  unknowns: ["지금 계신 곳 · 숙소 · 귀가 경로의 상태는 우리가 알 수 없어요", "공식 해제가 나왔는지는 재난문자 조회 기준이에요(놓칠 수 있어요)"],
  affected_districts: ["종로구"],
  items: [
    { item_id: "i-1", title: "경복궁 관람", kind: "activity", starts_at: "2026-10-06T07:00:00+00:00", place_name: "경복궁", district: "종로구", status: "affected", reason: "공식 재난문자가 종로구를 지정했어요" },
    { item_id: "i-2", title: "성수동 카페", kind: "dining", starts_at: "2026-10-06T09:00:00+00:00", place_name: "성수 카페", district: null, status: "unknown", reason: "이 장소의 구를 알 수 없어요" },
    { item_id: "i-3", title: "N서울타워", kind: "activity", starts_at: "2026-10-06T11:00:00+00:00", place_name: "N서울타워", district: "용산구", status: "unaffected", reason: "공식 재난문자가 지정한 구(종로구) 밖이에요" },
  ],
  counts: { affected: 1, unknown: 1, unaffected: 1 },
  options: [
    { key: "keep", label: "그대로 이어가기", detail: "일정은 바꾸지 않아요" },
    { key: "replace_affected", label: "영향받은 것만 바꾸기", recommended: true, detail: "영향이 확정된 곳마다 대신 갈 곳을 제안해요. 고르시면 바뀌고, 안 고르시면 그대로예요" },
    { key: "replan_all", label: "남은 일정 새로 받기", detail: "개인 AI에게 이 상황을 넘겨 남은 일정을 다시 짜게 해요" },
  ],
  extras: [{ key: "lighter_day", label: "오늘은 가볍게", default: false, detail: "하루를 덜 채워 달라는 선택이에요. 우리가 임의로 낮추지 않고, 고르시면 기록하고 에이전트에게 전해요" }],
  questions: [
    { key: "lodging", text: "숙소와 귀가 경로는 이용할 수 있나요?", answers: ["yes", "no", "unknown"] },
    { key: "companions", text: "함께하는 분(아이 · 어르신)이 있나요?", answers: ["yes", "no"] },
  ],
  constraints: { avoid_districts: ["종로구"], affected_item_ids: ["i-1"], unknown_item_ids: ["i-2"], lighter_day: false },
  scope_note: "우리는 일정(시간표)만 조정해요. 업체 예약은 바꾸지 않아요.",
  chosen: null,
};

/** GET …/safety/recovery gives `brief` (or none); POST …/safety/recovery gives `answer` and its body is kept. */
async function stage(page: Page, state: { brief: unknown; answer?: Record<string, unknown>; posts: Record<string, unknown>[] }) {
  await page.route(`**/v1/web/trips/${TRIP_ID}/safety/recovery`, async (route) => {
    if (route.request().method() === "POST") {
      state.posts.push(route.request().postDataJSON() as Record<string, unknown>);
      await route.fulfill({ json: state.answer ?? { recorded: true, choice: "keep", lighter_day: false, proposals: [] } });
      return;
    }
    await route.fulfill({ json: { recovery: state.brief } });
  });
}
/** `[2026-10-07 목업 C안]` 재난 뒤 이어가기는 종 아래 알림 칸에 있다. */
async function openTrip(page: Page) {
  await start(page);
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(tripScreen(page)).toBeVisible();
  await openNotices(page);
}
const panel = (page: Page) => page.getByTestId("recovery-panel");

test("다시 시작한 정지가 없으면 패널이 없다(꾸러미가 null 이거나 서버에 아직 없을 때 — 404 — 도 조용히 없다)", async ({ page }) => {
  await stage(page, { brief: null, posts: [] });
  await openTrip(page);
  await expect(panel(page)).toHaveCount(0);
});

test("꾸러미가 있으면 아는 것과 모르는 것을 나눠 보이고, 남은 일정마다 영향을 말하며 — 모르는 것은 「범위 모름」이지 「영향 없음」이 아니다", async ({ page }) => {
  await stage(page, { brief: BRIEF, posts: [] });
  await openTrip(page);
  await expect(panel(page)).toBeVisible();
  await expect(panel(page).getByRole("heading", { name: "재난 뒤 이어가기" })).toBeVisible();
  await expect(panel(page)).toContainText("호우");
  await expect(panel(page).getByRole("heading", { name: "알려진 것" })).toBeVisible();
  await expect(panel(page)).toContainText("행정안전부 긴급재난문자: 종로구 호우 대피 안내");                       // 출처가 붙은 사실
  await expect(panel(page).getByRole("heading", { name: "우리가 모르는 것" })).toBeVisible();
  await expect(panel(page)).toContainText("지금 계신 곳 · 숙소 · 귀가 경로의 상태는 우리가 알 수 없어요");
  await expect(panel(page)).toContainText("영향 확정 1곳 · 범위 모름 1곳 · 영향 없음 1곳");
  const rows = panel(page).locator("li[data-status]");
  await expect(rows).toHaveCount(3);
  await expect(rows.filter({ hasText: "경복궁 관람" })).toContainText("영향 확정");
  await expect(rows.filter({ hasText: "성수동 카페" })).toContainText("범위 모름");
  await expect(rows.filter({ hasText: "성수동 카페" })).not.toContainText("영향 없음");                         // 모르면 불명
  await expect(rows.filter({ hasText: "성수동 카페" })).toContainText("이 장소의 구를 알 수 없어요");           // 서버가 말한 이유
  await expect(rows.filter({ hasText: "N서울타워" })).toContainText("영향 없음");
  await expect(rows.filter({ hasText: "N서울타워" })).toContainText("공식 재난문자가 지정한 구(종로구) 밖이에요");
});

test("세 가지 길이 서 있고 아무것도 미리 골라져 있지 않다 — 추천 표시만 있고, 하나를 골라야 정할 수 있으며, 못 하는 것은 서버 문장 그대로 보인다", async ({ page }) => {
  await stage(page, { brief: BRIEF, posts: [] });
  await openTrip(page);
  const options = panel(page).getByRole("radio");
  await expect(options).toHaveCount(3);
  for (const option of await options.all()) await expect(option).not.toBeChecked();                        // 우리가 대신 고르지 않는다
  await expect(panel(page).getByRole("radio", { name: /영향받은 것만 바꾸기/ })).toBeVisible();
  await expect(panel(page).locator("label").filter({ hasText: "영향받은 것만 바꾸기" })).toContainText("추천");
  await expect(panel(page).locator("label").filter({ hasText: "그대로 이어가기" })).not.toContainText("추천");
  await expect(panel(page).getByRole("checkbox", { name: /오늘은 가볍게/ })).not.toBeChecked();             // 밀도를 우리가 임의로 낮추지 않는다
  await expect(panel(page)).toContainText("우리는 일정(시간표)만 조정해요. 업체 예약은 바꾸지 않아요.");        // 서버 문장 그대로
  const confirm = panel(page).getByRole("button", { name: "이대로 정하기" });
  await expect(confirm).toBeDisabled();
  await panel(page).getByRole("radio", { name: /그대로 이어가기/ }).check();
  await expect(confirm).toBeEnabled();
});

test("고르면 선택 · 「오늘은 가볍게」 · 답한 질문만 서버로 가고, 영향 확정 항목의 제안 결과(후보 있음 · 후보 없음)를 일정은 그대로라고 말하며 보인다", async ({ page }) => {
  const state = {
    brief: BRIEF, posts: [] as Record<string, unknown>[],
    answer: { recorded: true, choice: "replace_affected", lighter_day: true, proposals: [
      { item_id: "i-1", title: "경복궁 관람", status: "requested_options", proposal_id: "prop-1", options: ["국립중앙박물관", "서울역사박물관"] },
      { item_id: "i-9", title: "북촌 산책", status: "no_alternate", proposal_id: null, options: [] },
    ] },
  };
  await stage(page, state);
  await openTrip(page);
  await panel(page).getByRole("radio", { name: /영향받은 것만 바꾸기/ }).check();
  await panel(page).getByRole("checkbox", { name: /오늘은 가볍게/ }).check();
  await panel(page).getByRole("group", { name: "숙소와 귀가 경로는 이용할 수 있나요?" }).getByRole("button", { name: "예" }).click();
  await panel(page).getByRole("button", { name: "이대로 정하기" }).click();
  await expect.poll(() => state.posts.length).toBe(1);
  expect(state.posts[0]).toEqual({ pause_id: "pause-1", choice: "replace_affected", lighter_day: true, answers: { lodging: "yes" } });   // 답하지 않은 질문은 보내지 않는다
  const done = panel(page).getByRole("status");
  await expect(done).toContainText("영향받은 것만 바꾸기");
  await expect(done).toContainText("오늘은 가볍게");
  await expect(done).toContainText("「경복궁 관람」: 대신 갈 곳 2곳을 제안했어요");
  await expect(done).toContainText("고르면 바뀌고, 안 고르면 그대로예요");
  await expect(done).toContainText("「북촌 산책」: 대신 갈 곳 후보가 없어서 일정은 그대로 두었어요");
  await expect(done.getByRole("button", { name: "다시 고르기" })).toBeVisible();
});

test("서버가 선택을 기록하지 못했다고 하면(recorded=false) 조용히 넘기지 않고 알림으로 알린다 — 일정은 그대로라고 함께", async ({ page }) => {
  await stage(page, { brief: BRIEF, posts: [], answer: { recorded: false, choice: "keep", lighter_day: false, proposals: [] } });
  await openTrip(page);
  await panel(page).getByRole("radio", { name: /그대로 이어가기/ }).check();
  await panel(page).getByRole("button", { name: "이대로 정하기" }).click();
  const notice = page.getByRole("status").filter({ hasText: "선택을 기록하지 못했어요" });
  await expect(notice).toBeVisible();
  await expect(notice).toContainText("일정은 그대로예요");
});

test("이미 고른 것이 있으면(chosen) 고른 것을 보여 주고, 다시 고르기를 누르면 그 값이 채워진 채 열린다", async ({ page }) => {
  await stage(page, { brief: { ...BRIEF, chosen: { pause_id: "pause-1", choice: "keep", lighter_day: true, answers: { companions: "no" } } }, posts: [] });
  await openTrip(page);
  const done = panel(page).getByRole("status");
  await expect(done).toContainText("그대로 이어가기");
  await expect(done).toContainText("오늘은 가볍게");
  await done.getByRole("button", { name: "다시 고르기" }).click();
  await expect(panel(page).getByRole("radio", { name: /그대로 이어가기/ })).toBeChecked();
  await expect(panel(page).getByRole("checkbox", { name: /오늘은 가볍게/ })).toBeChecked();
  await expect(panel(page).getByRole("group", { name: "함께하는 분(아이 · 어르신)이 있나요?" }).getByRole("button", { name: "아니요" })).toHaveAttribute("aria-pressed", "true");
});

test("시작 전 여행(upcoming)의 꾸러미는 서버가 쓴 그 범위 문장(날짜 연기 · 취소는 예약처에서)을 그대로 보인다", async ({ page }) => {
  const scope = "우리는 일정(시간표)만 조정해요. 아직 시작하지 않은 여행의 날짜 연기 · 취소와 업체 예약은 예약처에서 직접 하셔야 해요.";
  await stage(page, { brief: { ...BRIEF, phase: "upcoming", scope_note: scope }, posts: [] });
  await openTrip(page);
  await expect(panel(page)).toHaveAttribute("data-phase", "upcoming");
  await expect(panel(page)).toContainText(scope);
});

test("「일정 다시 시작」의 답에 꾸러미가 실려 오면 곧바로 패널이 서고(다시 읽지 않아도), 정지 패널은 사라진다", async ({ page }) => {
  let paused = true;
  await page.route(`**/v1/web/trips/${TRIP_ID}`, async (route) => {
    if (route.request().method() !== "GET") { await route.continue(); return; }
    const response = await route.fetch();
    const trip = await response.json();
    trip.safety = paused ? { paused: true, level: "day", label: "호우 — 오늘 남은 일정 정지", since: "2026-10-06T05:05:00Z", until: null, day: "2026-10-06", released: false, resume: { label: "일정 다시 시작", path: "/safety/resume" } } : { paused: false };
    await route.fulfill({ response, json: trip });
  });
  await page.route(`**/v1/web/trips/${TRIP_ID}/safety/resume`, async (route) => {
    paused = false;
    await route.fulfill({ json: { resumed: 1, safety: { paused: false }, recovery: BRIEF } });
  });
  // 서버의 GET 은 다시 시작한 정지가 있으면 같은 꾸러미를 준다(여기서는 시작 전에는 없다).
  await page.route(`**/v1/web/trips/${TRIP_ID}/safety/recovery`, async (route) => { await route.fulfill({ json: { recovery: paused ? null : BRIEF } }); });
  await start(page);
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(page.getByTestId("safety-panel")).toBeVisible();
  await expect(panel(page)).toHaveCount(0);                                                                // 정지 중에는 꾸러미가 아직 없다
  await page.getByTestId("safety-panel").getByRole("button", { name: "일정 다시 시작" }).click();
  await expect(page.getByTestId("safety-panel")).toHaveCount(0);
  await openNotices(page);                                                                                  // 꾸러미는 종 아래 알림 칸에
  await expect(panel(page)).toBeVisible();
});
