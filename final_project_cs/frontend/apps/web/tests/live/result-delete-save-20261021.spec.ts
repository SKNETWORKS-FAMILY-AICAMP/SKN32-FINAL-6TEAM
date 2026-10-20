import { expect, test } from "@playwright/test";
import { mockServer, start } from "./helpers";

/**
 * `[2026-10-21 사용자 결정 — 결과 화면 삭제는 바로 저장만]` 결과 화면에서 삭제를 누르면 곧바로 서버에 저장만 한다(`removed: true` · `check: false`) — 새로고침해도 삭제가 남고 「다시 제출」도 남는다.
 * 지금 화면 안에서는 회색 「삭제 예정」 카드와 「되돌리기」가 그대로, 새로고침 뒤에는 그 일정이 빠진 채로 보인다 — 테스트용 모방 서버로 도는 자동 시험(실제 서버 아님).
 * 모방 서버의 `saveOnly: "on"` 은 저장만 한 판을 `review.checked: false` 로 돌려준다(서버 계약 web-intakes.md 「check: false」).
 */
const INTAKE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";

test("삭제한 뒤 새로고침하면 그 일정은 빠진 채로 보이고 「다시 제출」이 남는다 — 「다시 제출」은 빼기를 다시 보내지 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.reset();
  await server.scenario({ review: "on", board: "calm", saveOnly: "on", readingPolls: 0 });
  await start(page);
  await page.goto(`/intakes/${INTAKE}`);
  await expect(page.locator('main[data-stage="done"]')).toBeVisible({ timeout: 15_000 });
  const market = page.getByRole("article", { name: "광장시장", exact: true });
  await page.getByRole("button", { name: "광장시장 삭제" }).click();
  await expect(market).toContainText("삭제 예정");
  await expect.poll(async () => (await server.received("POST", "/edits")).length).toBe(1);
  await page.reload();
  await expect(page.locator('main[data-stage="done"]')).toBeVisible({ timeout: 15_000 });
  await expect(market).toHaveCount(0);
  await page.getByRole("button", { name: "다시 제출" }).click();
  await expect.poll(async () => (await server.received("POST", "/revalidate")).length).toBe(1);
  await expect(page.getByRole("button", { name: "여행 등록" })).toBeVisible();
  expect(await server.received("POST", "/edits")).toHaveLength(1);
});
