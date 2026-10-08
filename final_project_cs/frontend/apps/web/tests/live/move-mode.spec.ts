import { expect, test, type Page } from "@playwright/test";
import { mockServer } from "./helpers";
import { needsBadge, openFinished, toast } from "./plan-check-kit";

/**
 * `[2026-10-07 사용자 지시 — 이동수단 고르기]` 확인 결과의 이동 줄을 펼치면 맨 위에 「이동 수단」 박스. 열면 서버에 **그 구간 하나**만 묻고, 지하철 · 버스 · 택시 · 걸음을 서버 순서 그대로 보인다(시간 · 요금 · 여유, 안 닿는 줄은 회색 +
 * 이유). 닿는 수단을 고르면 서버가 그 구간을 다시 계산해 확인 결과 전체를 돌려주고(다시 제출 불필요), 알림에 「되돌리기」가 선다. ★서버(이동 세션)에는 아직 이 경로가 없어서 테스트용 mock 서버가 계약안 모양을 흉내 낸다(화면 반응 —
 * 실서버 확인 아님). 첫 구간(경복궁 → 올리브영)은 지하철로 39분 늦고 택시 · 걸음은 닿는다.
 */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const FIRST = 'li[data-type="move"][data-entry-id="0-0:0-1"]';
const first = (page: Page) => page.locator(FIRST);
const box = (page: Page) => first(page).getByRole("button", { name: /^이동 수단/ });
const ways = (page: Page) => first(page).getByRole("listbox", { name: "이동 수단 고르기" });
async function openMove(page: Page) { await first(page).getByRole("button", { name: /지하철 3호선.*9분/ }).click(); }

test("서버가 이 기능을 모르면(404) 박스는 눌러 보는 순간 사라진다 — 가짜 목록을 만들지 않고, 다시 열어도 다시 묻지 않는다", async ({ page, request }) => {
  const server = await openFinished(page, request);                                                   // moveOptions: off
  await openMove(page);
  await box(page).click();
  await expect(box(page)).toHaveCount(0);
  await expect(ways(page)).toHaveCount(0);
  expect(await server.received("GET", "/moves/0-0~0-1/options")).toHaveLength(1);
  await expect(first(page).getByText("올리브영 인사동점을 임시로 골라서 계산했어요")).toBeVisible();     // 이동 칸의 나머지는 그대로
});

test("박스를 열면 그 구간 하나만 묻고 네 줄이 응답 순서로 나온다 — 택시 예상 요금과 고지 · 여유 · 늦어요 · 안 닿는 줄은 회색 + 이유", async ({ page, request }) => {
  const server = await openFinished(page, request, undefined, { moveOptions: "on" });
  await openMove(page);
  await expect(box(page)).toContainText("지하철 3호선");                                                // 지금 수단
  expect(await server.received("GET", "/options")).toHaveLength(0);                                   // 열기 전에는 아무것도 부르지 않는다
  await box(page).click();
  const rows = ways(page).getByRole("option");
  await expect(rows).toHaveCount(4);
  expect(await server.received("GET", "/options")).toHaveLength(1);
  expect((await server.received("GET", "/options"))[0].path).toContain("/moves/0-0~0-1/options");    // 이 구간 하나만
  expect((await server.received("GET", "/options"))[0].query).toBe("?revision=1");                 // 보고 있는 판을 싣는다(이동 세션 구현)
  await expect(rows.nth(0)).toContainText("지하철");
  await expect(rows.nth(0)).toContainText("추천");
  await expect(rows.nth(0)).toContainText("1,550원");
  await expect(rows.nth(0)).toContainText("여유 21분");
  await expect(rows.nth(0)).toHaveAttribute("aria-selected", "true");                                 // 지금 쓰는 수단
  await expect(rows.nth(1)).toContainText("버스");
  await expect(rows.nth(1)).toContainText("늦어요 1분");                                              // 닿지 않는다
  await expect(rows.nth(1)).toContainText("고를 수 없어요");
  await expect(rows.nth(1)).toHaveAttribute("aria-disabled", "true");
  await expect(rows.nth(1)).toContainText("다음 일정이 11:00에 시작해요");                              // 서버가 쓴 이유 그대로
  await expect(rows.nth(2)).toContainText("택시");
  await expect(rows.nth(2)).toContainText("예상 9,000원");
  await expect(rows.nth(2)).toContainText("실제 결제액은 교통·대기·호출료·할증에 따라 달라질 수 있어요");
  await expect(rows.nth(2)).toContainText("추정");
  await expect(rows.nth(2)).toContainText("여유 25분");
  await expect(rows.nth(3)).toContainText("걸음");
  await expect(rows.nth(3)).toContainText("요금 없음");
  // 닫았다 다시 열어도 다시 묻지 않는다(같은 판)
  await box(page).click();
  await box(page).click();
  await expect(rows).toHaveCount(4);
  expect(await server.received("GET", "/options")).toHaveLength(1);
});

test("닿는 수단(택시)을 고르면 한 번의 요청으로 그 구간이 바뀌고 — 목록이 닫히고 알림 + 되돌리기 · 확인 필요가 하나 줄고 · 다시 제출은 켜지지 않는다 — 되돌리기는 원래 수단을 고른다", async ({ page, request }) => {
  const server = await openFinished(page, request, undefined, { moveOptions: "on" });
  await expect(needsBadge(page)).toHaveAccessibleName("확인 필요 2곳");
  await openMove(page);
  await box(page).click();
  await ways(page).getByRole("option", { name: /택시/ }).click();
  await expect.poll(async () => (await server.received("POST", "/mode")).length).toBe(1);
  expect((await server.received("POST", "/mode"))[0].body).toEqual({ revision: 1, mode: "taxi" });
  await expect(ways(page)).toHaveCount(0);                                                           // 목록은 닫힌다
  const note = toast(page, "택시로 바꿨어요");
  await expect(note).toBeVisible();
  await expect(note.getByRole("button", { name: "되돌리기" })).toBeVisible();
  await expect(first(page).getByRole("button", { name: /택시 5분/ })).toBeVisible();                   // 이동 줄이 바뀐 수단으로
  await expect(box(page)).toContainText("내가 고름");
  await expect(needsBadge(page)).toHaveAccessibleName("확인 필요 1곳");                                 // 늦던 구간이 풀렸다
  expect(await server.received("POST", "/revalidate")).toHaveLength(0);                              // 다시 제출이 필요 없다
  // 되돌리기: 원래 수단(지하철)을 고르는 것과 같다
  await note.getByRole("button", { name: "되돌리기" }).click();
  await expect.poll(async () => (await server.received("POST", "/mode")).length).toBe(2);
  expect((await server.received("POST", "/mode"))[1].body).toMatchObject({ mode: "subway" });
});

test("안 닿는 줄을 누르면 서버가 쓴 이유가 알림으로 나오고 아무것도 보내지 않는다 — 계산을 못 끝낸 수단은 「확인 못 함」(늦어요가 아니다)", async ({ page, request }) => {
  const server = await openFinished(page, request, undefined, { moveOptions: "partial" });
  await openMove(page);
  await box(page).click();
  const rows = ways(page).getByRole("option");
  await expect(rows.nth(1)).toContainText("확인 못 함");
  await expect(rows.nth(1)).not.toContainText("늦어요");
  await rows.nth(1).click({ force: true });                                                          // 회색 줄은 aria-disabled 라 눌러도 이유만 말한다
  await expect(toast(page, "계산이 오래 걸려 확인하지 못했어요")).toBeVisible();
  expect(await server.received("POST", "/mode")).toHaveLength(0);
});

test("아무 수단도 안 닿으면 줄은 모두 회색이고 「여유 안에 닿는 수단이 없어요」 + 「시간 고치기」 단추가 선다", async ({ page, request }) => {
  await openFinished(page, request, undefined, { moveOptions: "none" });
  await openMove(page);
  await box(page).click();
  for (const row of await ways(page).getByRole("option").all()) await expect(row).toHaveAttribute("aria-disabled", "true");
  await expect(ways(page)).toContainText("여유 안에 닿는 수단이 없어요");
  await ways(page).getByRole("option").nth(0).click({ force: true });                                // 안 닿는 이유는 알림으로
  await expect(toast(page, "다음 일정이 11:00에 시작해요")).toBeVisible();
  await ways(page).getByRole("button", { name: "시간 고치기" }).click();
  await expect(ways(page)).toHaveCount(0);
});

test("서버가 못 읽어 주면 서버 문장과 「다시 불러오기」, 모르는 수단은 줄에서 빠진다, 찾는 동안 「찾는 중」", async ({ page, request }) => {
  await openFinished(page, request, undefined, { moveOptions: "fail" });
  await openMove(page);
  await box(page).click();
  await expect(ways(page).getByRole("alert")).toContainText("서버 오류");
  await expect(ways(page).getByRole("button", { name: "다시 불러오기" })).toBeVisible();
});

test("모르는 수단을 서버가 같이 보내도 네 줄만 나온다", async ({ page, request }) => {
  await openFinished(page, request, undefined, { moveOptions: "unknown_mode" });
  await openMove(page);
  await box(page).click();
  await expect(ways(page).getByRole("option")).toHaveCount(4);
});

test("서버 계산이 오래 걸리는 동안은 「찾는 중…」 줄이 서고 안내 문장이 있으며, 끝나면 줄이 채워진다", async ({ page, request }) => {
  await openFinished(page, request, undefined, { moveOptions: "slow" });
  await openMove(page);
  await box(page).click();
  await expect(ways(page)).toContainText("찾는 중…");
  await expect(ways(page).getByRole("status")).toContainText("이 구간의 이동 수단을 찾고 있어요");
  await expect(ways(page).getByRole("option")).toHaveCount(4, { timeout: 12_000 });
});

test("키보드: 박스에서 Enter 로 열고 화살표로 줄을 오가며 Esc 로 닫으면 초점이 박스로 돌아온다", async ({ page, request }) => {
  await openFinished(page, request, undefined, { moveOptions: "on" });
  await openMove(page);
  await box(page).focus();
  await page.keyboard.press("Enter");
  const rows = ways(page).getByRole("option");
  await expect(rows).toHaveCount(4);
  await rows.nth(0).focus();
  await page.keyboard.press("ArrowDown");
  await expect(rows.nth(1)).toBeFocused();
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("ArrowUp");
  await expect(rows.nth(3)).toBeFocused();                                                           // 맨 위에서 위로 가면 맨 아래로 돈다
  await page.keyboard.press("Escape");
  await expect(ways(page)).toHaveCount(0);
  await expect(box(page)).toBeFocused();
});

test("삭제 예정 일정 옆 구간은 박스가 잠기고 이유를 말한다 · 320px 폭에서도 목록이 가로로 넘치지 않는다", async ({ page, request }) => {
  await openFinished(page, request, undefined, { moveOptions: "on" });
  await page.getByRole("button", { name: "올리브영 삭제" }).click();                                    // 올리브영 앞뒤 이동은 잠긴다
  await openMove(page);
  await expect(box(page)).toHaveAttribute("aria-disabled", "true");
  await box(page).click({ force: true });
  await expect(toast(page, "삭제할 일정 앞뒤의 이동이라 바꿀 수 없어요")).toBeVisible();
  await expect(ways(page)).toHaveCount(0);
});

test("320px 폭에서 목록이 가로로 넘치지 않는다", async ({ page, request }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await openFinished(page, request, undefined, { moveOptions: "on" });
  await openMove(page);
  await box(page).click();
  await expect(ways(page).getByRole("option")).toHaveCount(4);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const list = (await ways(page).boundingBox())!;
  expect(list.x + list.width).toBeLessThanOrEqual(320);
});

test("목록에서는 닿는다던 수단을 서버가 다시 계산해 받지 않으면(422) 서버가 쓴 이유를 목록 안에 보이고, 화면의 계획은 그대로다", async ({ page, request }) => {
  const server = await openFinished(page, request, undefined, { moveOptions: "refuse" });
  await openMove(page);
  await box(page).click();
  await ways(page).getByRole("option", { name: /택시/ }).click();
  await expect.poll(async () => (await server.received("POST", "/mode")).length).toBe(1);
  await expect(ways(page).getByRole("alert")).toContainText("다시 계산해 보니 택시로도 다음 일정에 늦어요");   // `why` 그대로(「그 수단은 고를 수 없어요」 가 아니다)
  await expect(first(page).getByRole("button", { name: /지하철 3호선.*9분/ })).toBeVisible();        // 이동 줄은 그대로
});
