import { expect, test, type Page } from "@playwright/test";
import { mockServer } from "./helpers";
import { openFinished } from "./plan-check-kit";

/**
 * `[2026-10-23 사용자 지시 — 경로 후보 먼저 3개 · 내리면 더]` 이동 수단 상자를 열면 검사에 실린 경로 후보 3개가 바로 보이고, 목록 끝이 화면에 들어오면 다음 후보를 부른다.
 * 배포 직후처럼 서버가 「계산이 오래 걸려」(빈 쪽)로 답하면 화면이 몇 초 뒤 한 번 저절로 다시 부른다(x600 실측: 첫 번 25초 0건 · 다시 6초 5건).
 * ★테스트용 mock 서버가 계약 모양을 흉내 낸다(화면 반응 — 실서버 확인 아님).
 */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const FIRST = 'li[data-type="move"][data-entry-id="0-0:0-1"]';
const first = (page: Page) => page.locator(FIRST);
const box = (page: Page) => first(page).getByRole("button", { name: /^이동 수단/ });
const ways = (page: Page) => first(page).getByRole("listbox", { name: "이동 수단 고르기" });
async function openMove(page: Page) { await first(page).getByRole("button", { name: /지하철 3호선.*9분/ }).click(); }

test("경로 후보 3개가 상자를 열자마자 보이고, 끝까지 내리면 다음 2개를 불러와 끝을 알린다", async ({ page, request }) => {
  const server = await openFinished(page, request, undefined, { moveOptions: "on", moveRoutes: "on" });
  await openMove(page);
  await box(page).click();
  await expect(ways(page).getByText("경로 후보")).toBeVisible();
  await expect(ways(page).getByRole("option", { name: /버스 01A → 3호선/ })).toBeVisible();
  await ways(page).getByRole("option", { name: /버스 01A → 3호선/ }).scrollIntoViewIfNeeded();
  await expect(ways(page).getByRole("option", { name: /버스 종로11/ })).toBeVisible();
  await expect(ways(page).getByRole("option", { name: /5호선 → 3호선/ })).toContainText("조금 일찍 출발");
  await expect(ways(page).getByText("찾은 경로를 다 보여 드렸어요")).toBeVisible();
  const asked = await server.received("GET", "/routes");
  expect(asked).toHaveLength(1);
  expect(asked[0].query).toContain("offset=3");
});

test("배포 직후처럼 첫 「더 보기」가 「오래 걸려」로 빈 답이면, 몇 초 뒤 저절로 한 번 다시 불러 후보를 보인다", async ({ page, request }) => {
  const server = await openFinished(page, request, undefined, { moveOptions: "on", moveRoutes: "cold" });
  await openMove(page);
  await box(page).click();
  await ways(page).getByRole("option", { name: /버스 01A → 3호선/ }).scrollIntoViewIfNeeded();
  await expect(ways(page).getByText("아직 찾고 있어요 · 곧 다시 불러와요")).toBeVisible();
  await expect(ways(page).getByRole("alert")).toHaveCount(0);                                           // 오류 문장 · 「다시 불러오기」를 먼저 보이지 않는다
  await expect(ways(page).getByRole("option", { name: /버스 종로11/ })).toBeVisible({ timeout: 10_000 });
  expect(await server.received("GET", "/routes")).toHaveLength(2);                                      // 한 번만 다시 불렀다
});
