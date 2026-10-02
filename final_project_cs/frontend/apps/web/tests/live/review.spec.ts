import { expect, test, type Page } from "@playwright/test";
import { mockServer, start, TRIP_ID } from "./helpers";

/**
 * 계획 확인 화면(2026-10-02 목업) — 테스트용 모방 서버로 도는 자동 시험(실제 서버 아님). 실제 서버로 본 것은 리포트에 따로 적는다.
 * 모방 서버의 `board: "rich"` 는 장소 셋(올리브영이 확인 필요)과 이동 둘이다.
 */
const INTAKE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const row = (page: Page, id: string) => page.locator(`div[data-item="${id}"]`);
const name = (page: Page, text: string) => page.getByRole("button", { name: text, exact: true });

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

/** 이미 읽힌 접수를 바로 연다(읽는 중 화면을 건너뛴다). */
async function openFinished(page: Page, request: Parameters<typeof mockServer>[0], change: Record<string, unknown> = {}) {
  const server = mockServer(request);
  await server.scenario({ board: "rich", readingPolls: 0, ...change });
  await start(page);
  await page.goto(`/intakes/${INTAKE}`);
  await expect(name(page, "경복궁")).toBeVisible();
  return server;
}

test("읽는 중에는 서버가 흘려 주는 대로 줄이 읽히고 카드·검사 줄이 차례로 나타나며, 끝나면 접힌 결과 화면이 된다 (실시간 진행)", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ board: "rich", intakeEvents: "on", readingPolls: 1 });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill("10/1 09:00 경복궁 관람");
  await page.getByRole("button", { name: "계획 확인하기" }).click();

  // 읽는 화면: 원문이 한 줄씩 읽힌다
  await expect(page.getByRole("heading", { name: "계획을 확인하고 있어요" })).toBeVisible();
  await expect(page.getByText("→ 1일차 09:00 · 경복궁 관람")).toBeVisible();
  // 지도 화면으로 넘어가 장소 카드가 차례로 생기고, 끝나면 접힌 결과 화면 (제목 + 확인 필요 요약)
  await expect(page.getByText("장소·운영시간 확인").first()).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("장소 1곳 · 이동 1구간 확인 필요")).toBeVisible({ timeout: 25_000 });
  await expect(page.getByRole("heading", { name: "내 여행" })).toBeVisible();
  expect((await server.received("GET", `${INTAKE}/events`)).length).toBeGreaterThan(0);
  // 스트림이 일을 했으니 1.5초 폴링은 필요 없었다: 접수 조회는 처음 한 번과 끝난 뒤 한 번뿐이다
  expect((await server.received("GET", INTAKE)).length).toBeLessThanOrEqual(4);
});

test("실시간 진행이 열렸다가 아무 소식도 없으면(6초) 「연결이 끊겼어요」를 알리고 폴링으로 끝까지 따라간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ board: "rich", intakeEvents: "silent", readingPolls: 8 });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill("10/1 09:00 경복궁 관람");
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page.getByText("연결이 끊겼어요", { exact: false })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("장소 1곳 · 이동 1구간 확인 필요")).toBeVisible({ timeout: 30_000 });
});

test("서버에 실시간 진행이 없으면(404) 조용히 폴링으로 읽는다", async ({ page, request }) => {
  await mockServer(request).scenario({ board: "rich", intakeEvents: "off", readingPolls: 2 });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill("10/1 09:00 경복궁 관람");
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page.getByText("장소 1곳 · 이동 1구간 확인 필요")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("연결이 끊겼어요", { exact: false })).toHaveCount(0);
});

test("결과 화면: 카드는 유지·조정·확인 필요를 보이고, 누르면 서버의 검사 줄이 펼쳐지며, 이동 줄을 누르면 경로·수단·도착이 보인다", async ({ page, request }) => {
  await openFinished(page, request);
  await expect(page.getByText("장소 1곳 · 이동 1구간 확인 필요")).toBeVisible();
  await expect(row(page, "0-0").getByText("유지")).toBeVisible();
  await expect(row(page, "0-1").getByText("확인 필요")).toBeVisible();
  await expect(row(page, "0-2").getByText("조정")).toBeVisible();
  await name(page, "경복궁").click();
  await expect(page.getByText("09:00–17:00 안에 머물러요")).toBeVisible();
  await page.getByRole("button", { name: /이동 지하철 3호선/ }).click();
  await expect(page.getByText("일정보다 39분 늦어요")).toBeVisible();
  // 모르는 값은 「–」로 두고 통과로 그리지 않는다 (확인 필요 카드의 시간 줄은 주의)
  await name(page, "올리브영 인사동점").click();
  await expect(page.getByText("경복궁 관람과 30분 겹쳐요")).toBeVisible();
});

test("잠금: 확인이 끝난 일정은 고정되고 서버에 알리며, 확인이 필요한 일정은 이유를 말하고 보내지 않는다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await row(page, "0-0").locator('button[data-act="lock"]').click();
  await expect(page.getByText("경복궁을 꼭 넣을 일정으로 고정했어요")).toBeVisible();
  const [lock] = await server.received("POST", "/edits");
  expect(lock.body).toEqual({ revision: 1, edits: [{ source_id: "s1", field: "items[0].locked", value: true }] });
  await expect(row(page, "0-0").locator('button[data-act="lock"]')).toHaveAttribute("aria-pressed", "true");

  // 못 쓰는 단추는 흐리게 두되 눌러 볼 수 있다(이유를 말하려고) — 플레이라이트는 그런 단추를 안 누르므로 힘으로 누른다
  await row(page, "0-1").locator('button[data-act="lock"]').click({ force: true });
  await expect(page.getByText("확인이 필요한 일정은 먼저 고쳐야 고정할 수 있어요")).toBeVisible();
  expect((await server.received("POST", "/edits")).length).toBe(1);               // 보내지 않았다
});

test("삭제: 질문을 먼저 하고(취소가 처음 초점, Esc도 취소), 삭제하면 서버에 알리며 「되돌리기」로 다시 살린다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await row(page, "0-2").locator('button[data-act="delete"]').click();
  const dialog = page.getByRole("alertdialog");
  await expect(dialog).toContainText("광장시장 일정을 삭제하시겠습니까?");
  await expect(dialog).toContainText("1일차 12:30–13:30");
  await expect(dialog.getByRole("button", { name: "취소" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  expect((await server.received("POST", "/edits")).length).toBe(0);
  await expect(row(page, "0-2").locator('button[data-act="delete"]')).toBeFocused();   // 초점이 누른 단추로 돌아온다

  await row(page, "0-2").locator('button[data-act="delete"]').click();
  await page.getByRole("alertdialog").getByRole("button", { name: "삭제" }).click();
  await expect(page.getByText("광장시장 일정을 삭제했어요")).toBeVisible();
  await expect(name(page, "광장시장")).toHaveCount(0);
  const [removed] = await server.received("POST", "/edits");
  expect(removed.body).toEqual({ revision: 1, edits: [{ source_id: "s1", field: "items[2].removed", value: true }] });

  await page.getByRole("button", { name: "되돌리기" }).click();
  await expect(name(page, "광장시장")).toBeVisible();
  const edits = await server.received("POST", "/edits");
  expect(edits[1].body).toEqual({ revision: 2, edits: [{ source_id: "s1", field: "items[2].removed", value: false }] });
});

test("수정 화면: 후보 카드를 넘겨 「이 장소로 바꾸기」를 누르면 좌표까지 서버로 가고, 화면이 닫히며 되돌리기가 뜬다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await name(page, "올리브영 인사동점").click();
  await row(page, "0-1").getByRole("button", { name: "수정" }).last().click();
  await expect(page.getByLabel("장소 검색")).toBeVisible();
  await expect(page.getByText("올리브영 인사동점 바꾸기")).toBeVisible();
  await expect(page.getByText("대체 후보 A · 1순위")).toBeVisible();
  await expect(page.getByText("올리브영 광화문점").first()).toBeVisible();

  await page.getByRole("button", { name: "후보 A 올리브영 광화문점" }).click();         // 지도의 핀을 누르면 그 카드가 앞으로 온다
  await expect(page.getByText("대체 후보 A · 2/3")).toBeVisible();
  await page.getByRole("button", { name: "이 장소로 바꾸기" }).first().click();
  await expect(page.getByLabel("장소 검색")).toHaveCount(0);
  await expect(page.getByText("올리브영 인사동점을 올리브영 광화문점으로 바꿨어요")).toBeVisible();
  const [edit] = await server.received("POST", "/edits");
  expect(edit.body).toEqual({ revision: 1, edits: [{ source_id: "s1", field: "items[1].place",
    value: { name: "올리브영 광화문점", latitude: 37.5717, longitude: 126.9791, source: "kakao" } }] });
});

test("수정 화면: 검색하면 결과가 나오고, 고른 곳이 「검색으로 고른 곳」 카드로 들어오며, 사진 없는 곳은 없다고 말한다", async ({ page, request }) => {
  await openFinished(page, request);
  await name(page, "광장시장").click();
  await row(page, "0-2").getByRole("button", { name: "수정" }).last().click();
  // 관광공사 번호가 있는 지금 장소는 등록 사진과 출처가 보인다
  await expect(page.getByRole("img", { name: "경복궁_1" })).toBeVisible();
  await expect(page.getByRole("region", { name: "등록된 사진" }).getByText("ⓒ한국관광공사")).toBeVisible();

  const box = page.getByLabel("장소 검색");
  await box.fill("올");
  await expect(page.getByText("두 글자 이상 적어 주세요")).toBeVisible();
  await box.fill("올리브영");
  await expect(page.getByText("‘올리브영’ 검색 결과 1곳")).toBeVisible();
  await page.getByRole("button", { name: /올리브영 명동 플래그십/ }).click();
  await expect(page.getByText("검색으로 고른 곳 A")).toBeVisible();
  await expect(page.getByText("검색으로 고른 곳 · 2/")).toBeVisible();
  await expect(page.getByText("이 장소는 사진 정보가 없어요", { exact: false })).toBeVisible();   // 카카오 장소 — 지어내지 않는다
});

test("수정 화면의 날짜·시각 고치기: 바뀐 칸만 서버로 간다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await name(page, "광장시장").click();
  await row(page, "0-2").getByRole("button", { name: "수정" }).last().click();
  await page.getByText("날짜·시각 고치기").click();
  await page.getByLabel("시작").fill("12:45");
  await page.getByRole("button", { name: "저장" }).click();
  await expect(page.getByLabel("장소 검색")).toHaveCount(0);
  const [edit] = await server.received("POST", "/edits");
  expect(edit.body).toEqual({ revision: 1, edits: [{ source_id: "s1", field: "items[2].starts_at", value: "12:45" }] });
});

test("맨 아래: 전체 자동 추천 → 재검증 → 여행 등록 순서로 이어지고, 확인할 것이 남으면 재검증은 이유를 말한다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  const auto = page.getByRole("button", { name: /전체 자동 추천/ });
  await expect(auto).toContainText("2");                                            // 고칠 항목 수: 장소 1 + 이동 1
  const recheck = page.getByRole("button", { name: "재검증" });
  await expect(recheck).toHaveAttribute("aria-disabled", "true");
  await recheck.click({ force: true });
  await expect(page.getByText("확인이 필요한 항목 2건이 남아 있어요")).toBeVisible();
  expect((await server.received("POST", "/revalidate")).length).toBe(0);

  await auto.click();
  await expect(page.getByText("확인이 필요한 2건을 검증된 대체 일정으로 바꿨어요")).toBeVisible();
  await expect(page.getByText("올리브영 인사동점 → 올리브영 광화문점 11:45–12:15")).toBeVisible();
  const [fixed] = await server.received("POST", "/autofix");
  expect(fixed.body).toEqual({ revision: 1 });
  await expect(page.getByText("고칠 곳이 없어요")).toBeVisible();

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
  await row(page, "0-2").locator('button[data-act="delete"]').click();
  await page.getByRole("alertdialog").getByRole("button", { name: "삭제" }).click();
  await expect(page.getByText("고정한 일정이라 바꿀 수 없어요").first()).toBeVisible();
  await expect(name(page, "광장시장")).toBeVisible();
});

test("영어 화면: 같은 화면이 영어로 보이고, 서버가 쓴 문장은 번역하지 않고 그대로 둔다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ board: "rich", readingPolls: 0 });
  await page.addInitScript(() => localStorage.setItem("tripilot.web.settings.v1", JSON.stringify({ language: "en", navigation: "fixed" })));
  await start(page);
  await page.goto(`/intakes/${INTAKE}`);
  await expect(page.getByText("1 place · 1 leg to review")).toBeVisible();
  await expect(page.getByRole("button", { name: "Auto-fix all" })).toBeVisible();
  await expect(row(page, "0-1").getByText("Needs review")).toBeVisible();
  await name(page, "올리브영 인사동점").click();
  await expect(page.getByText("경복궁 관람과 30분 겹쳐요")).toBeVisible();          // 서버 문장은 그대로
});
