import { expect, test, type Page } from "@playwright/test";
import { agree, hydrated, mockServer, openRegistration, useKorean } from "./helpers";

/**
 * `[2026-10-25 사용자 결정 — 예시 불러오기 첫 안내 A안]` 첫 여행(이 브라우저에 등록한 여행이 없고 입력칸이 빈)이면 화면을 덮고 「예시 불러오기」 → 「계획 확인하기」를 두 단계로 안내한다.
 * 끝내거나 닫으면 이 브라우저에서 다시 띄우지 않는다. 목업 `mockups/tripilot-registration-example-guide.html`. 모방 서버 시험 — 화면 동작만 본다.
 * ★다른 시험은 `start()` 가 이 안내를 본 것으로 넣어 둔다 — 여기서는 처음 한 번만 지운다(다시 열었을 때 「본 것」이 남는지도 본다).
 */
test.beforeEach(async ({ page, request }) => {
  await mockServer(request).reset();
  await useKorean(page);
  await agree(page);
  await page.addInitScript(() => {
    if (sessionStorage.getItem("example-guide-reset")) return;
    localStorage.removeItem("tripilot.web.example-guide.v1");
    sessionStorage.setItem("example-guide-reset", "1");
  });
});

const first = (page: Page) => page.getByRole("dialog", { name: "예시로 한 번 해 보세요" });
const second = (page: Page) => page.getByRole("dialog", { name: "「계획 확인하기」를 눌러 검증해 보세요" });

test("첫 여행이면 덮개가 「예시 불러오기」를 비추고, 누르면 예시가 채워진 뒤 「계획 확인하기」를 비춘다 — 닫으면 다시 뜨지 않는다", async ({ page }) => {
  await openRegistration(page);
  await expect(first(page)).toBeVisible();
  await expect(first(page)).toContainText("「예시 불러오기」를 눌러 일정 예시를 불러오고, 「계획 확인하기」로 장소 · 운영시간 · 이동을 검증해 보세요.");
  await first(page).getByRole("button", { name: "예시 불러오기" }).click();
  await expect(page.getByLabel("나의 여행 계획")).toHaveValue(/^1일차 · \d{4}-\d{2}-\d{2}\n10:00 국립현대미술관 서울/);
  await expect(second(page)).toBeVisible();
  await expect(second(page).getByRole("button", { name: "계획 확인하기" })).toBeFocused();
  await second(page).getByRole("button", { name: "닫기" }).click();
  await expect(second(page)).toHaveCount(0);
  expect((await mockServer(page.request).log()).filter((entry) => entry.method === "POST")).toEqual([]);   // 안내는 아무것도 보내지 않는다
  await page.getByLabel("나의 여행 계획").fill("");
  await page.reload();
  await hydrated(page);
  await page.waitForTimeout(800);                                                    // 여행 목록을 읽은 뒤에 정한다 — 그 뒤에도 뜨지 않는다
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("「직접 쓸게요」나 Esc 로 닫으면 입력칸에 초점이 가고 아무것도 채우지 않는다", async ({ page }) => {
  await openRegistration(page);
  await first(page).getByRole("button", { name: "직접 쓸게요" }).click();
  await expect(first(page)).toHaveCount(0);
  await expect(page.getByLabel("나의 여행 계획")).toBeFocused();
  await expect(page.getByLabel("나의 여행 계획")).toHaveValue("");
  await page.evaluate(() => sessionStorage.removeItem("example-guide-reset"));   // 다시 열 때 `beforeEach` 의 스크립트가 「본 것」을 한 번 더 지운다
  await page.reload();
  await expect(first(page)).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(first(page)).toHaveCount(0);
  await expect(page.getByLabel("나의 여행 계획")).toHaveValue("");
});

test("작성 중이던 글이 입력칸에 있으면 안내를 띄우지 않는다", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("tripilot.web.registration-draft.v1", "1일차 · 2026-11-02\n10:00 경복궁"));
  await openRegistration(page);
  await page.waitForTimeout(800);
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
