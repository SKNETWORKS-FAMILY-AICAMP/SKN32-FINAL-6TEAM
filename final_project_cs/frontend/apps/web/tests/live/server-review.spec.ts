import { expect, test, type Page } from "@playwright/test";
import { mockServer, start, TRIP_ID, checkPlan } from "./helpers";
import { head, needsBadge } from "./plan-check-kit";

/**
 * 계획 확인 화면(조직 판 `features/plan-check`)에 서버의 확인 결과(`review`)를 이은 부분 — 테스트용 모방 서버로 도는 자동 시험(실제 서버 아님).
 * 실제 서버로 본 것은 리포트에 따로 적는다. 모방 서버의 `review: "on"` 이 서버의 확인 결과를 내고, `board: "rich"` 는 장소 셋(올리브영이 확인 필요)과
 * 이동 둘이다. `review` 를 안 내는 서버(`review: "absent"`)의 화면은 조직 쪽 시험(`intake-review.spec.ts`)이 맡는다.
 */
const INTAKE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const card = (page: Page, title: string) => page.getByRole("article", { name: title });

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

/** 이미 읽힌 접수를 바로 연다(읽는 중 화면을 건너뛴다). */
async function openFinished(page: Page, request: Parameters<typeof mockServer>[0], change: Record<string, unknown> = {}) {
  const server = mockServer(request);
  await server.scenario({ review: "on", board: "rich", readingPolls: 0, ...change });
  await start(page);
  await page.goto(`/intakes/${INTAKE}`);
  await expect(needsBadge(page)).toBeVisible();
  return server;
}

async function uploadPlan(page: Page) {
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill("10/1 09:00 경복궁 관람");
  await checkPlan(page);
}

test("읽는 동안 서버의 내용 이벤트로 장소 카드와 검사 줄이 차례로 채워지고, 끝나면 서버의 판정이 그대로 보인다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ review: "on", board: "rich", intakeEvents: "on", readingPolls: 1 });
  await start(page);
  await uploadPlan(page);

  await expect(needsBadge(page)).toBeVisible({ timeout: 40_000 });
  await expect(card(page, "경복궁 관람")).toBeVisible();
  await expect(card(page, "올리브영")).toContainText("확인 필요");
  await expect(card(page, "광장시장")).not.toContainText("조정");                                    // 「조정」은 더 말하지 않는다
  expect((await server.received("GET", `${INTAKE}/events`)).length).toBeGreaterThan(0);
  // 스트림이 일을 했으니 1.5초 폴링은 필요 없었다: 접수 조회는 처음 한 번과 끝난 뒤 몇 번뿐이다
  expect((await server.received("GET", INTAKE)).length).toBeLessThanOrEqual(5);
});

test("실시간 진행이 열렸다가 아무 소식도 없으면 「연결이 끊겼어요」를 알리고 폴링으로 끝까지 따라간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ review: "on", board: "rich", intakeEvents: "silent", readingPolls: 8 });
  await start(page);
  await uploadPlan(page);
  await expect(page.getByText("연결이 끊겼어요", { exact: false })).toBeVisible({ timeout: 20_000 });
  await expect(needsBadge(page)).toBeVisible({ timeout: 40_000 });
});

test("결과: 카드는 서버의 판정(확인 필요만 말한다)과 검사 줄을 그대로 보이고, 이동 줄은 경로·수단·도착을 보인다", async ({ page, request }) => {
  await openFinished(page, request);
  await expect(card(page, "경복궁 관람")).not.toContainText("확인 필요");
  await card(page, "경복궁 관람").getByRole("heading").getByRole("button").click();
  await expect(page.getByText("09:00–17:00 안에 머물러요")).toBeVisible();
  await expect(page.getByText("화요일 휴무 · 방문은 목요일")).toBeVisible();
  await card(page, "올리브영").getByRole("heading").getByRole("button").click();
  await expect(page.getByText("경복궁 관람과 30분 겹쳐요")).toBeVisible();     // 서버가 쓴 문장 그대로
  await expect(page.getByRole("button", { name: /지하철 3호선.*9분 · 0\.6km/ })).toBeVisible();      // 수단은 아이콘, 눈에 보이는 말은 시간과 거리
});

test("잠금: 확인이 끝난 일정은 서버에 알리고 고정되며, 확인이 필요한 일정은 이유를 말하고 보내지 않는다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await head(page, "경복궁 관람").click();
  await page.getByRole("button", { name: "경복궁 관람 꼭 넣을 일정으로 고정" }).click();
  await expect(page.getByText("경복궁 관람을 꼭 넣을 일정으로 고정했어요")).toBeVisible();
  const [lock] = await server.received("POST", "/edits");
  expect(lock.body).toEqual({ revision: 1, edits: [{ source_id: "s1", field: "items[0].locked", value: true }] });   // 잠금은 혼자 간다
  await expect(page.getByRole("button", { name: "경복궁 관람 고정 풀기" })).toBeVisible();

  await head(page, "올리브영").click();
  await page.getByRole("button", { name: "확인이 필요한 일정은 고정할 수 없어요" }).click({ force: true });
  await expect(page.getByText("확인이 필요한 일정은 먼저 고쳐야 고정할 수 있어요")).toBeVisible();
  expect((await server.received("POST", "/edits")).length).toBe(1);               // 보내지 않았다
});

test("삭제 → 되돌리기: 삭제는 표시만 하고 되돌리기는 서버로 가지 않으며, 다시 제출할 때 빼기가 서버로 간다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await page.getByRole("button", { name: "광장시장 삭제" }).click();
  await expect(card(page, "광장시장")).toContainText("삭제 예정");
  expect(await server.received("POST", "/edits")).toHaveLength(0);
  await page.getByRole("button", { name: "광장시장 삭제 되돌리기" }).click();
  await expect(card(page, "광장시장")).not.toContainText("삭제 예정");
  expect(await server.received("POST", "/edits")).toHaveLength(0);                                 // 되돌리기도 서버와 상관없다
  await page.getByRole("button", { name: "광장시장 삭제" }).click();
  await page.getByRole("button", { name: "다시 제출" }).click();
  await expect(card(page, "광장시장")).toHaveCount(0);
  const [removed] = await server.received("POST", "/edits");
  expect(removed.body).toEqual({ revision: 1, edits: [{ source_id: "s1", field: "items[2].removed", value: true }] });
  expect((await server.received("POST", "/revalidate")).length).toBe(1);                           // 이어서 전체를 다시 확인한다
});

test("수정 화면: 예약한 일정은 서버가 후보를 주지 않고(booked_needs_name) 화면은 그 이유와 이름을 쓰라는 안내를 말한다 — 일반 「다른 후보가 없어요」가 아니다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await server.scenario({ candidateNotes: ["booked_needs_name"] });
  await page.getByRole("button", { name: "올리브영 수정" }).click();
  await expect(page.getByText("올리브영 바꾸기")).toBeVisible();
  await expect(page.getByText("예약하신 곳이라 다른 후보를 권하지 않아요")).toBeVisible();
  await expect(page.getByText("다른 후보가 없어요 · 위 검색창에서 찾아 바꿀 수 있어요")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "이 장소로 바꾸기" })).toHaveCount(0);         // nothing to change to until the name is typed above
});

test("수정 화면: 서버의 대체 후보가 순위·거리와 함께 나오고, 바꾸면 좌표까지 서버로 가며, 되돌리기는 이전 장소를 다시 보낸다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await page.getByRole("button", { name: "올리브영 수정" }).click();
  await expect(page.getByText("올리브영 바꾸기")).toBeVisible();
  await expect(page.getByText("대체 후보 A · 1순위")).toBeVisible();
  await expect(page.getByText("경복궁에서 0.5km")).toBeVisible();
  // `[2026-10-03]` the card says what the server gave: here it named no kind for the candidate, and the card does not guess one
  await expect(page.getByText("이 장소의 종류 정보가 없어요").first()).toBeVisible();
  expect((await server.received("GET", "/candidates")).length).toBe(1);

  await page.getByRole("button", { name: "이 장소로 바꾸기" }).first().click();
  await expect(page.getByText("올리브영을 올리브영 광화문점으로 바꿨어요")).toBeVisible();
  const [edit] = await server.received("POST", "/edits");
  expect(edit.body).toEqual({ revision: 1, edits: [{ source_id: "s1", field: "items[1].place",
    value: { name: "올리브영 광화문점", latitude: 37.5717, longitude: 126.9791, source: "kakao" } }] });

  await page.getByRole("button", { name: "되돌리기" }).click();
  await expect.poll(async () => (await server.received("POST", "/edits")).length).toBe(2);
  const [, undo] = await server.received("POST", "/edits");
  expect(undo.body).toEqual({ revision: 2, edits: [{ source_id: "s1", field: "items[1].place",
    value: { name: "올리브영 인사동점", latitude: 37.5741, longitude: 126.9857, source: "kakao" } }] });
});

test("같은 판에서는 대체 후보를 한 번만 받는다 — 수정 화면을 닫았다 다시 열어도 다시 묻지 않고 바로 보인다", async ({ page, request }) => {
  // `[2026-10-07 사용자 지적 — 이미 받은 대안인데 다시 열면 로딩이 있다]`
  const server = await openFinished(page, request);
  await page.getByRole("button", { name: "올리브영 수정" }).click();
  await expect(page.getByText("대체 후보 A · 1순위")).toBeVisible();
  await page.getByRole("button", { name: "바꾸기 그만두기" }).click();
  await expect(page.getByText("올리브영 바꾸기")).toHaveCount(0);
  await page.getByRole("button", { name: "올리브영 수정" }).click();
  await expect(page.getByText("대체 후보 A · 1순위")).toBeVisible();
  expect((await server.received("GET", "/candidates")).length).toBe(1);                         // 두 번째는 받아 둔 것
});

test("대체 후보는 서버가 고른 단(같은 종류 · 비슷한 경험 · 식사 시간 식당)과 이유 한 문장을 보이고, 식사 시간 식당을 고르면 일정 종류도 식사로 같이 보낸다", async ({ page, request }) => {
  // `[2026-10-07 서버 c0ca7054]` 후보마다 basis · reason. meal_inferred 를 고르면 items[i].kind = "dining" 을 장소와 함께(안 보내면 식당이 활동 일정에 들어간다)
  const server = await openFinished(page, request, { candidateBasis: "on" });
  await page.getByRole("button", { name: "올리브영 수정" }).click();
  await expect(page.getByText("같은 종류", { exact: true })).toBeVisible();
  await expect(page.getByText("올리브영 인사동점과 같은 중분류(관광공사 분류)의 곳이에요 · 경복궁에서 450m · 다음 일정까지 8분 여유가 있어요")).toBeVisible();
  await page.getByRole("button", { name: "후보 C", exact: true }).click();                    // 셋째 후보 카드로
  const meal = page.getByRole("article", { name: "광장시장 순희네 빈대떡" });
  await expect(meal.getByText("식사 시간 식당")).toBeVisible();
  await expect(meal.getByText("점심 시간의 시장 일정이라 시장 안 식당도 함께 보여 드려요")).toBeVisible();
  await meal.getByRole("button", { name: "이 장소로 바꾸기" }).click();
  await expect.poll(async () => (await server.received("POST", "/edits")).length).toBe(1);
  const [edit] = await server.received("POST", "/edits");
  expect((edit.body as { edits: { field: string; value: unknown }[] }).edits).toEqual(expect.arrayContaining([
    expect.objectContaining({ field: "items[1].place" }),
    { source_id: "s1", field: "items[1].kind", value: "dining" },
  ]));
});

test("이름 없는 「호텔」 줄은 숙소와 숙소 안 식사가 짝으로 나오고(꼬리표 「숙소」 · 「숙소 안 식사」), 숙소 안 식사를 고르면 일정 종류를 식사로 같이 보낸다", async ({ page, request }) => {
  // `[2026-10-07 사용자 지시 · 서버 90d9e403]` 그냥 「호텔」은 아침에 나서는 숙소일 수도, 그 안에서 조식을 먹을 수도 있다 — 둘 다 후보에
  const server = await openFinished(page, request, { candidateBasis: "lodging" });
  await page.getByRole("button", { name: "올리브영 수정" }).click();
  await page.getByRole("button", { name: "후보 A", exact: true }).click();
  await expect(page.getByText("숙소", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "후보 B", exact: true }).click();
  await expect(page.getByText("숙소 안 식사", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("숙소 안 식당이 있는지는 확인하지 못했어요")).toBeVisible();
  await page.getByRole("article").filter({ hasText: "숙소 안 식당이 있는지는 확인하지 못했어요" }).getByRole("button", { name: "이 장소로 바꾸기" }).click();
  await expect.poll(async () => (await server.received("POST", "/edits")).length).toBe(1);
  const [edit] = await server.received("POST", "/edits");
  expect((edit.body as { edits: { field: string; value: unknown }[] }).edits).toEqual(expect.arrayContaining([{ source_id: "s1", field: "items[1].kind", value: "dining" }]));
});

test("장소 검색과 사진: 검색 결과가 나오고, 관광공사 번호가 있는 곳은 사진과 「ⓒ한국관광공사」 출처가 보인다", async ({ page, request }) => {
  await openFinished(page, request);
  await page.getByRole("button", { name: "광장시장 수정" }).click();
  await expect(page.getByText("광장시장 바꾸기")).toBeVisible();
  await expect(page.getByRole("img", { name: /광장시장.*ⓒ한국관광공사|ⓒ한국관광공사/ }).first()).toBeVisible();

  const box = page.getByLabel("장소 검색");
  await box.fill("올리브영");
  await expect(page.getByText("‘올리브영’ 검색 결과 1곳")).toBeVisible();
  const found = page.getByRole("button", { name: /올리브영 명동 플래그십/ });
  await expect(found).toBeVisible();
  await expect(found).toContainText("카카오 지도");                       // 어디서 찾았는지가 이름 옆에 작게
  await expect(found).toContainText("화장품 · 서울 중구 명동길 53");           // 서버가 준 분류 · 주소 그대로
});

test("맨 아래: 확인할 것이 남으면 「다시 제출」은 이유를 말하고, 전체 자동 추천의 수정안은 「여행 등록」으로 바로 저장·등록된다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  const auto = page.getByRole("button", { name: /전체 자동 추천/ });
  await expect(auto).toContainText("2");                                            // 고칠 항목 수: 장소 1 + 이동 1
  await page.getByRole("button", { name: "다시 제출" }).click({ force: true });               // 꺼진 단추도 눌러 볼 수 있다(이유를 말하려고)
  await expect(page.getByText(/확인이 필요한 항목 2건이 남아 있어요/)).toBeVisible();
  expect((await server.received("POST", "/revalidate")).length).toBe(0);

  await auto.click();
  await expect(page.getByText("올리브영 → 올리브영 광화문점 11:45–12:15")).toBeVisible();
  // `[2026-10-03]` first only SHOWN: the dry run saves nothing. `[2026-10-04]` The proposed plan is the server's own, already checked: 「여행 등록」 is not held back for an 「적용하기」.
  const [shown] = await server.received("POST", "/autofix");
  expect(shown.body).toEqual({ revision: 1, dry_run: true });
  expect((await server.received("POST", "/confirm")).length).toBe(0);
  await page.getByRole("button", { name: "여행 등록" }).click();
  await expect.poll(async () => (await server.received("POST", "/autofix")).length).toBe(2);   // 저장은 미리 보기와 같은 호출에서 dry_run 만 뺀 것
  const [, fixed] = await server.received("POST", "/autofix");
  expect(fixed.body).toEqual({ revision: 1 });
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));
  const [confirm] = await server.received("POST", "/confirm");
  expect(confirm.body).toEqual({ revision: 2 });                                               // 방금 저장한 판으로 등록했다
  expect((await server.received("POST", "/revalidate")).length).toBe(0);                       // 서버가 이미 확인한 수정안이라 다시 확인하지 않는다
});

test("서버가 고친 것을 거절하면(409 item_locked) 서버의 문장이 그대로 알림으로 뜨고 화면은 그대로다", async ({ page, request }) => {
  await openFinished(page, request, { editRefusal: "locked" });
  await page.getByRole("button", { name: "광장시장 삭제" }).click();
  await page.getByRole("button", { name: "다시 제출" }).click();                                      // 빼기는 다시 제출할 때 서버로 간다 — 거절당한다
  await expect(page.getByText("고정한 일정이라 바꿀 수 없어요").first()).toBeVisible();
  await expect(card(page, "광장시장")).toBeVisible();
});

test("서버의 확인 결과를 못 만들었으면(review: null) 못 만들었다고 말하고 읽은 값만 보인다 — 이동·자동 추천 같은 서버 일은 열지 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ review: "off", board: "rich", readingPolls: 0 });
  await start(page);
  await page.goto(`/intakes/${INTAKE}`);
  await expect(card(page, "경복궁 관람")).toBeVisible();
  await expect(page.getByText("서버가 장소·운영시간·이동 확인 결과를 만들지 못했어요", { exact: false })).toBeVisible();   // 못 만들었다고 말한다
  await expect(page.getByRole("button", { name: /전체 자동 추천/ })).toContainText("준비 중");
});

test("목록 끝에서 한 번 더 밀면 서버의 전체 자동 추천을 한 번 불러 수정안이 이어지고, 바뀐 일정에 「바뀜」이 붙는다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  const body = page.locator("div[class*=sheetBody]");
  await page.getByRole("button", { name: "목록 높이 바꾸기" }).click();
  await body.evaluate((element) => { element.scrollTop = element.scrollHeight; });
  await page.waitForTimeout(500);
  const box = (await body.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  for (let push = 0; push < 4; push += 1) { await page.mouse.wheel(0, 40); await page.waitForTimeout(50); }
  await expect(page.getByRole("heading", { name: "수정안" })).toBeVisible();
  await expect(page.getByText(/바뀜 · 이전/).first()).toBeVisible();
  const asked = await server.received("POST", "/autofix");
  expect(asked.length).toBe(1);                                                    // 밀기 한 번에 한 번만 부른다
  expect(asked[0].body).toEqual({ revision: 1, dry_run: true });                   // 그리고 저장하지 않는 미리 보기로만
  expect((await server.received("POST", "/edits")).length).toBe(0);
});

test("전체 자동 추천은 저장 없이 수정안만 보여 주고, 변경 전 쪽으로 돌아가면 변경 전 모습이 그대로 있다 — 서버에는 아무것도 저장되지 않았다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  const auto = page.getByRole("button", { name: /전체 자동 추천/ });
  await auto.click();
  await expect(page.getByRole("heading", { name: "수정안" })).toBeVisible();
  await expect(page.getByText(/바뀜 · 이전/).first()).toBeVisible();
  await page.getByRole("group", { name: "보는 일정" }).getByRole("button", { name: "1. 변경 전 일정" }).click();   // 변경 전 쪽으로 돌아간다
  await expect(page.getByRole("heading", { name: "계획 확인" })).toBeVisible();
  await expect(auto).toContainText("2");                                           // 고칠 항목 2건이 그대로 — 아무것도 저장되지 않았다
  const calls = await server.received("POST", "/autofix");
  expect(calls).toHaveLength(1);
  expect(calls[0].body).toEqual({ revision: 1, dry_run: true });
  expect((await server.received("POST", "/edits")).length).toBe(0);
});

test("고른 장소가 카드 이름이 된다 — 직접 고른 곳은 장소 이름으로 보이고, 쓴 글은 작게 남는다", async ({ page, request }) => {
  await openFinished(page, request, { board: "rich" });
  await page.getByRole("button", { name: "올리브영 수정" }).click();
  await expect(page.getByText("대체 후보 A · 1순위")).toBeVisible();
  await page.getByRole("button", { name: "이 장소로 바꾸기" }).first().click();
  await expect(card(page, "올리브영 광화문점")).toBeVisible();
  await expect(card(page, "올리브영 광화문점")).toContainText("원문 「올리브영」");
});

// ── 2026-10-03 사용자 요청 모음(확인 화면) ─────────────────────────────────────────────────────────────────────

test("머리의 「확인 필요」 글자를 누르면 확인이 필요한 곳만 모아 보이고, 「전체 보기」로 돌아온다", async ({ page, request }) => {
  await openFinished(page, request);
  const count = needsBadge(page);
  await expect(count).toHaveAttribute("aria-pressed", "false");
  await expect(card(page, "경복궁 관람")).toBeVisible();
  await count.click();
  await expect(count).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("확인이 필요한 곳만 보는 중이에요")).toBeVisible();
  await expect(card(page, "올리브영")).toBeVisible();                                    // 확인이 필요한 곳
  await expect(card(page, "경복궁 관람")).toHaveCount(0);                                 // 괜찮은 곳은 빠진다
  await expect(card(page, "광장시장")).toHaveCount(0);
  await page.getByRole("button", { name: "전체 보기" }).click();
  await expect(card(page, "경복궁 관람")).toBeVisible();
  await expect(card(page, "광장시장")).toBeVisible();
  await expect(count).toHaveAttribute("aria-pressed", "false");
});

test("머리의 「내 여행」을 눌러 계획 이름을 바꾸면 서버의 trip.title 로 가고 머리글이 새 이름이 된다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await page.getByRole("button", { name: /^계획 이름 · / }).click();                                // 이름을 누르면 연필이 나온다
  await page.getByRole("button", { name: /계획 이름 바꾸기/ }).click();
  const field = page.getByRole("textbox", { name: "계획 이름" });
  await field.fill("제주 3박 4일");
  await field.press("Enter");
  await expect(page.getByRole("heading", { name: "제주 3박 4일", level: 1 })).toBeVisible();
  const [saved] = await server.received("POST", "/edits");
  expect(saved.body).toEqual({ revision: 1, edits: [{ field: "trip.title", value: "제주 3박 4일" }] });
  // Esc 는 이름을 그대로 둔다
  await page.getByRole("button", { name: /^계획 이름 · / }).click();
  await page.getByRole("button", { name: /계획 이름 바꾸기/ }).click();
  await page.getByRole("textbox", { name: "계획 이름" }).fill("버릴 이름");
  await page.getByRole("textbox", { name: "계획 이름" }).press("Escape");
  await expect(page.getByRole("heading", { name: "제주 3박 4일", level: 1 })).toBeVisible();
  expect((await server.received("POST", "/edits")).length).toBe(1);
});

test("출처 줄(ⓒ한국관광공사)은 「계속 내리면 …」 안내 위에 있어서, 목록 맨 끝이 「내리면 다음이 나온다」로 읽힌다", async ({ page, request }) => {
  await openFinished(page, request);
  const credit = page.locator("details[class*=credit] summary");
  const hint = page.getByText("계속 내리면 권장 수정안이 반영된 모습을 보여 드려요");
  await expect(credit).toBeVisible();
  await hint.scrollIntoViewIfNeeded();
  const [creditBox, hintBox] = [await credit.boundingBox(), await hint.boundingBox()];
  expect(creditBox!.y).toBeLessThan(hintBox!.y);
});

test("전체 자동 추천이 바꿀 곳을 못 찾으면 이유만 말하지 않고, 사용자가 직접 고쳐야 하는 첫 곳을 열어 그 자리로 옮긴다", async ({ page, request }) => {
  const server = await openFinished(page, request, { autofix: "none" });
  const olive = card(page, "올리브영");
  await expect(olive.getByRole("button", { name: "올리브영", exact: true })).toHaveAttribute("aria-expanded", "false");
  await page.getByRole("button", { name: /전체 자동 추천/ }).click();
  await expect(page.getByText("바꿀 수 있는 대체 일정이 없어요")).toBeVisible();
  await expect(page.getByText("직접 고쳐야 하는 곳으로 옮겼어요")).toBeVisible();
  await expect(olive.getByRole("button", { name: "올리브영", exact: true })).toHaveAttribute("aria-expanded", "true");
  await expect(olive).toBeInViewport({ ratio: 0.5 });
  expect((await server.received("POST", "/edits")).length).toBe(0);                          // 아무것도 바뀌지 않았다
});

test("「전체 자동 추천」 미리 보기는 화면이 열릴 때 서버에서 이미 받아 두어, 누르거나 밀 때 서버를 다시 기다리지 않는다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await expect.poll(async () => (await server.received("POST", "/autofix")).length).toBe(1);   // 아무것도 누르기 전에 이미 한 번 불렀다
  const [early] = await server.received("POST", "/autofix");
  expect(early.body).toEqual({ revision: 1, dry_run: true });
  await page.getByRole("button", { name: /전체 자동 추천/ }).click();
  await expect(page.getByRole("heading", { name: "수정안" })).toBeVisible();
  expect((await server.received("POST", "/autofix")).length).toBe(1);                         // 눌러도 다시 부르지 않는다
});


test("사진을 두 가지로 읽은 일정: 두 읽기를 나란히 보이고, 고른 쪽을 그 일정의 이름으로 보내면 확인 필요가 풀린다", async ({ page, request }) => {
  // `[2026-10-07 cs 개발 세션 제안 계약]` 검토 항목의 `rereads[]` - 서버는 어느 쪽이 맞는지 모른다(다른 읽기가 맞는 일이 많았다). 고르는 것은 고객이다.
  const server = await openFinished(page, request, { reread: "on" });
  await expect(card(page, "청경궁 관람")).toContainText("확인 필요");
  await card(page, "청경궁 관람").getByRole("heading").getByRole("button").click();
  await expect(page.getByText("사진에서 이 줄을 두 가지로 읽었어요", { exact: false })).toBeVisible();     // 서버 문장 그대로
  const choices = page.getByRole("group", { name: "이름 — 사진에서 두 가지로 읽었어요" });
  await expect(choices.getByRole("button", { name: "「청경궁 관람」 그대로 두기" })).toBeVisible();
  await choices.getByRole("button", { name: "「창경궁 관람」 쪽으로 바꾸기" }).click();
  await expect.poll(async () => (await server.received("POST", "/edits")).length).toBe(1);
  const [pick] = await server.received("POST", "/edits");
  expect(pick.body).toEqual({ revision: 1, edits: [{ source_id: "s1", field: "items[0].title", value: "창경궁 관람" }] });
  await expect(card(page, "창경궁 관람")).toBeVisible();
  await expect(card(page, "창경궁 관람")).not.toContainText("확인 필요");
  await expect(page.getByRole("group", { name: "이름 — 사진에서 두 가지로 읽었어요" })).toHaveCount(0);
});

test("사진을 두 가지로 읽은 일정: 지금 값이 맞으면 같은 값을 보내 확인만 하고, 다른 읽기가 없는 서버 응답에는 단추가 없다", async ({ page, request }) => {
  const server = await openFinished(page, request, { reread: "on" });
  await card(page, "청경궁 관람").getByRole("heading").getByRole("button").click();
  await page.getByRole("button", { name: "「청경궁 관람」 그대로 두기" }).click();
  await expect.poll(async () => (await server.received("POST", "/edits")).length).toBe(1);
  const [keep] = await server.received("POST", "/edits");
  expect(keep.body).toEqual({ revision: 1, edits: [{ source_id: "s1", field: "items[0].title", value: "청경궁 관람" }] });
  await expect(card(page, "청경궁 관람")).not.toContainText("확인 필요");
});

test("사진을 두 가지로 읽었는데 다른 읽기의 값을 못 정했으면(other null) 서버 문장만 보이고 고르는 단추는 없다", async ({ page, request }) => {
  await openFinished(page, request, { reread: "note_only" });
  await card(page, "청경궁 관람").getByRole("heading").getByRole("button").click();
  await expect(page.getByText("사진에서 이 줄을 두 가지로 읽었어요", { exact: false })).toBeVisible();
  await expect(page.getByRole("group", { name: "이름 — 사진에서 두 가지로 읽었어요" })).toHaveCount(0);
});
