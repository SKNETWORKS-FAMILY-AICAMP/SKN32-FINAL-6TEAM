import { expect, test } from "@playwright/test";
import { mockServer, start } from "./helpers";

/**
 * `[2026-10-14 x600 실서버 확인]` 서비스 공지는 배경 정보라 요청 한 번이 끊겨도(화면 이동 · 잠깐의 연결 문제) 「서비스 공지를 확인하지 못했어요」 띠를 띄우지 않는다.
 * 두 번 더 묻고 그래도 못 받을 때만 띄운다. mock 서버 시험이다 — 공지 요청은 브라우저 안에서 가로채 끊거나 답한다(화면 반응).
 */
test.beforeEach(async ({ page, request }) => {
  await mockServer(request).reset();
  await start(page);
});

const failedBanner = (page: import("@playwright/test").Page) => page.getByRole("heading", { name: "서비스 공지를 확인하지 못했어요" });

test("공지 요청이 한 번 끊겨도 다시 물어 받으면 「확인하지 못했어요」 띠가 안 뜬다", async ({ page }) => {
  let calls = 0;
  await page.route("**/v1/web/support/notices", (route) => {
    calls += 1;
    return calls === 1 ? route.abort("aborted") : route.fulfill({ json: { notices: [], maintenance: { enabled: false, message: "" } } });
  });
  await page.goto("/trips");
  await expect.poll(() => calls, { timeout: 10_000 }).toBeGreaterThanOrEqual(2);                    // 다시 물었다
  await page.waitForTimeout(500);
  await expect(failedBanner(page)).toHaveCount(0);
});

test("세 번 모두 못 받으면 그때 「확인하지 못했어요」 띠가 뜨고, 「다시 확인」이 있다", async ({ page }) => {
  let calls = 0;
  await page.route("**/v1/web/support/notices", (route) => { calls += 1; return route.abort("failed"); });
  await page.goto("/trips");
  await page.waitForTimeout(500);
  await expect(failedBanner(page)).toHaveCount(0);                                                   // 첫 실패 바로는 안 뜬다
  await expect(failedBanner(page)).toBeVisible({ timeout: 10_000 });                                // 1초 · 2초 뒤 두 번 더 묻고 나서
  expect(calls).toBeGreaterThanOrEqual(3);
  await expect(page.getByRole("button", { name: "다시 확인", exact: true })).toBeVisible();
});
