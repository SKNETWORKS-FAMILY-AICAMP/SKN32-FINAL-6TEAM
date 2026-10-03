import { expect, test, type Page } from "@playwright/test";
import { mockServer, start, TRIP_ID } from "./helpers";

/**
 * 계획 확인 화면(조직 판 `features/plan-check`)에 서버의 확인 결과(`review`)를 이은 부분 — 테스트용 모방 서버로 도는 자동 시험(실제 서버 아님).
 * 실제 서버로 본 것은 리포트에 따로 적는다. 모방 서버의 `review: "on"` 이 서버의 확인 결과를 내고, `board: "rich"` 는 장소 셋(올리브영이 확인 필요)과
 * 이동 둘이다. `review` 를 안 내는 서버(`review: "absent"`)의 화면은 조직 쪽 시험(`intake-review.spec.ts`)이 맡는다.
 */
const INTAKE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const card = (page: Page, title: string) => page.getByRole("article", { name: title });
const SUMMARY = "장소 1곳 · 이동 1구간 확인 필요";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

/** 이미 읽힌 접수를 바로 연다(읽는 중 화면을 건너뛴다). */
async function openFinished(page: Page, request: Parameters<typeof mockServer>[0], change: Record<string, unknown> = {}) {
  const server = mockServer(request);
  await server.scenario({ review: "on", board: "rich", readingPolls: 0, ...change });
  await start(page);
  await page.goto(`/intakes/${INTAKE}`);
  await expect(page.getByText(SUMMARY, { exact: true })).toBeVisible();
  return server;
}

async function uploadPlan(page: Page) {
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill("10/1 09:00 경복궁 관람");
  await page.getByRole("button", { name: "계획 확인하기" }).click();
}

test("읽는 동안 서버의 내용 이벤트로 장소 카드와 검사 줄이 차례로 채워지고, 끝나면 서버의 판정이 그대로 보인다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ review: "on", board: "rich", intakeEvents: "on", readingPolls: 1 });
  await start(page);
  await uploadPlan(page);

  await expect(page.getByText(SUMMARY, { exact: true })).toBeVisible({ timeout: 40_000 });
  await expect(card(page, "경복궁 관람")).toBeVisible();
  await expect(card(page, "올리브영")).toContainText("확인 필요");
  await expect(card(page, "광장시장")).toContainText("조정");
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
  await expect(page.getByText(SUMMARY, { exact: true })).toBeVisible({ timeout: 40_000 });
});

test("결과: 카드는 서버의 판정(유지·조정·확인 필요)과 검사 줄을 그대로 보이고, 이동 줄은 경로·수단·도착을 보인다", async ({ page, request }) => {
  await openFinished(page, request);
  await expect(card(page, "경복궁 관람")).toContainText("유지");
  await card(page, "경복궁 관람").getByRole("heading").getByRole("button").click();
  await expect(page.getByText("09:00–17:00 안에 머물러요")).toBeVisible();
  await expect(page.getByText("화요일 휴무 · 방문은 목요일")).toBeVisible();
  await card(page, "올리브영").getByRole("heading").getByRole("button").click();
  await expect(page.getByText("경복궁 관람과 30분 겹쳐요")).toBeVisible();     // 서버가 쓴 문장 그대로
  await expect(page.getByText("지하철 3호선 9분 · 0.6km").first()).toBeVisible();
});

test("잠금: 확인이 끝난 일정은 서버에 알리고 고정되며, 확인이 필요한 일정은 이유를 말하고 보내지 않는다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await page.getByRole("button", { name: "경복궁 관람 꼭 넣을 일정으로 고정" }).click();
  await expect(page.getByText("경복궁 관람을 꼭 넣을 일정으로 고정했어요")).toBeVisible();
  const [lock] = await server.received("POST", "/edits");
  expect(lock.body).toEqual({ revision: 1, edits: [{ source_id: "s1", field: "items[0].locked", value: true }] });   // 잠금은 혼자 간다
  await expect(page.getByRole("button", { name: "경복궁 관람 고정 풀기" })).toBeVisible();

  await page.getByRole("button", { name: "확인이 필요한 일정은 고정할 수 없어요" }).click({ force: true });
  await expect(page.getByText("확인이 필요한 일정은 먼저 고쳐야 고정할 수 있어요")).toBeVisible();
  expect((await server.received("POST", "/edits")).length).toBe(1);               // 보내지 않았다
});

test("삭제 → 되돌리기: 삭제는 서버에 알리고, 되돌리기는 같은 일정을 다시 살리는 수정을 보낸다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await page.getByRole("button", { name: "광장시장 삭제" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: /^삭제/ }).click();
  await expect(card(page, "광장시장")).toHaveCount(0);
  const [removed] = await server.received("POST", "/edits");
  expect(removed.body).toEqual({ revision: 1, edits: [{ source_id: "s1", field: "items[2].removed", value: true }] });

  await page.getByRole("button", { name: "되돌리기" }).click();
  await expect(card(page, "광장시장")).toBeVisible();
  const edits = await server.received("POST", "/edits");
  expect(edits[1].body).toEqual({ revision: 2, edits: [{ source_id: "s1", field: "items[2].removed", value: false }] });
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

test("맨 아래: 전체 자동 추천 → 재검증 → 여행 등록 순서로 이어지고, 확인할 것이 남으면 재검증은 이유를 말한다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  const auto = page.getByRole("button", { name: /전체 자동 추천/ });
  await expect(auto).toContainText("2");                                            // 고칠 항목 수: 장소 1 + 이동 1
  await page.getByRole("button", { name: "재검증" }).click({ force: true });                   // 꺼진 단추도 눌러 볼 수 있다(이유를 말하려고)
  await expect(page.getByText(/확인이 필요한 항목 2건이 남아 있어요/)).toBeVisible();
  expect((await server.received("POST", "/revalidate")).length).toBe(0);

  await auto.click();
  await expect(page.getByText("올리브영 → 올리브영 광화문점 11:45–12:15")).toBeVisible();
  const [fixed] = await server.received("POST", "/autofix");
  expect(fixed.body).toEqual({ revision: 1 });

  // 화면은 고친 일정을 하나씩 다시 확인하는 모습으로 따라간다 — 끝나면 「고칠 곳이 없어요」
  await expect(page.getByText("고칠 곳이 없어요")).toBeVisible({ timeout: 20_000 });
  // 고친 것이 있으니 바로 등록하지 않고 다시 확인한다
  await expect(page.getByRole("button", { name: "여행 등록" })).toHaveCount(0);
  await page.getByRole("button", { name: "재검증" }).click();
  await expect(page.getByText("재검증을 통과했어요")).toBeVisible();
  const [again] = await server.received("POST", "/revalidate");
  expect(again.body).toEqual({ revision: 2 });
  await page.getByRole("button", { name: "여행 등록" }).click();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));
  const [confirm] = await server.received("POST", "/confirm");
  expect(confirm.body).toEqual({ revision: 2 });
});

test("서버가 고친 것을 거절하면(409 item_locked) 서버의 문장이 그대로 알림으로 뜨고 화면은 그대로다", async ({ page, request }) => {
  await openFinished(page, request, { editRefusal: "locked" });
  await page.getByRole("button", { name: "광장시장 삭제" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: /^삭제/ }).click();
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

test("목록 끝에서 한 번 더 밀면 서버의 전체 자동 추천을 한 번 불러 권장 수정안이 반영된 모습으로 넘어가고, 바뀐 일정에 「바뀜」이 붙는다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  const body = page.locator("div[class*=sheetBody]");
  await page.getByRole("button", { name: "목록 높이 바꾸기" }).click();
  await body.evaluate((element) => { element.scrollTop = element.scrollHeight; });
  await page.waitForTimeout(500);
  const box = (await body.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  for (let push = 0; push < 4; push += 1) { await page.mouse.wheel(0, 40); await page.waitForTimeout(50); }
  await expect(page.getByRole("status").filter({ hasText: "권장 수정안을 반영한 모습이에요" })).toBeVisible();
  await expect(page.getByText(/바뀜 · 이전/).first()).toBeVisible();
  expect((await server.received("POST", "/autofix")).length).toBe(1);             // 밀기 한 번에 한 번만 부른다
});

test("고른 장소가 카드 이름이 된다 — 직접 고른 곳은 장소 이름으로 보이고, 쓴 글은 작게 남는다", async ({ page, request }) => {
  await openFinished(page, request, { board: "rich" });
  await page.getByRole("button", { name: "올리브영 수정" }).click();
  await expect(page.getByText("대체 후보 A · 1순위")).toBeVisible();
  await page.getByRole("button", { name: "이 장소로 바꾸기" }).first().click();
  await expect(card(page, "올리브영 광화문점")).toBeVisible();
  await expect(card(page, "올리브영 광화문점")).toContainText("원문 「올리브영」");
});
