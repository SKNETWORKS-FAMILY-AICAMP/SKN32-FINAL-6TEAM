import { expect, test, type Page } from "@playwright/test";
import { noHorizontalScroll, useKorean } from "./helpers/app";

/**
 * The plan-check screen on its preview page (`/preview/plan-check`) — the mockup's example data played on a clock, not a
 * server. The backend wires the real route; these tests hold the screen's own behaviour.
 */
test.beforeEach(async ({ page }) => { await useKorean(page); });

const sheet = (page: Page) => page.getByRole("region", { name: /장소·운영시간 확인|계획 확인/ });
const card = (page: Page, name: string) => page.getByRole("article", { name, exact: true });

test("원문을 한 줄씩 읽고, 지도 아래 목록에서 장소·이동을 하나씩 확인한 뒤, 카드가 접히고 여행 제목으로 끝난다", async ({ page }) => {
  await page.goto("/preview/plan-check");
  await expect(page.getByText("미리보기 · 예시 데이터 · 서버 미연결")).toBeVisible();
  await expect(page.getByRole("heading", { name: "계획을 확인하고 있어요", level: 1 })).toBeVisible();

  // ①② Lines are read one at a time; each read line says what it became.
  await expect(page.getByText("→ 1일차 11:00 · 올리브영")).toBeVisible();
  await expect(page.getByText("찾은 일정 4개")).toBeVisible();

  // ③ Map and list: the counts know the whole (4 places, 2 moves) before every card is shown.
  await expect(sheet(page).getByRole("heading", { name: "장소·운영시간 확인" })).toBeVisible();
  await expect(sheet(page).getByText(/장소 \d\/4 · 이동 \d\/2/)).toBeVisible();
  await expect(card(page, "경복궁").getByText("관광공사 정보로 찾았어요")).toBeVisible();

  // ④ Done: the title replaces the bar, the cards fold, what needs a look is counted and marked.
  await expect(page.getByRole("heading", { name: "10월 서울 여행", level: 1 })).toBeVisible({ timeout: 25_000 });
  await expect(sheet(page).getByText("장소 1곳 · 이동 1구간 확인 필요")).toBeVisible();
  await expect(card(page, "올리브영").getByText("확인 필요")).toBeVisible();
  await expect(card(page, "광장시장").getByText("조정")).toBeVisible();
  await expect(card(page, "경복궁").getByText("유지")).toBeVisible();
  await expect(card(page, "경복궁").getByText("관광공사 정보로 찾았어요")).toHaveCount(0);
  await expect(page.getByText("위치 미정 · 올리브영")).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "확인을 마쳤어요." })).toBeAttached();
});

test("움직임 줄이기 설정이면 다시 그리지 않고 서버 결과를 바로 보인다", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/preview/plan-check");
  // The example's last snapshot comes at 1.5 s; drawn at once, it is there well before the paced replay (about 12 s) would end.
  await expect(page.getByRole("heading", { name: "10월 서울 여행", level: 1 })).toBeVisible({ timeout: 4_000 });
  await expect(sheet(page).getByText("장소 1곳 · 이동 1구간 확인 필요")).toBeVisible();
});

test("「결과 바로 보기」는 다시 재생하지 않고 결과를 그리고, 「처음부터 재생」은 읽기 화면부터 다시 한다", async ({ page }) => {
  await page.goto("/preview/plan-check");
  await page.getByRole("button", { name: "결과 바로 보기" }).click();
  await expect(page.getByRole("heading", { name: "10월 서울 여행", level: 1 })).toBeVisible();
  await expect(page.getByRole("progressbar")).toHaveCount(0);           // the title has replaced the bar
  await page.getByRole("button", { name: "처음부터 재생" }).click();
  await expect(page.getByRole("progressbar", { name: "계획 확인 진행" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "계획을 확인하고 있어요", level: 1 })).toBeVisible();
});

test("뒤로 가기는 계획 입력 화면으로 간다", async ({ page }) => {
  await page.goto("/preview/plan-check");
  await page.getByRole("button", { name: "뒤로" }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
});

test("PC 기기 틀·375px·320px에서 읽기 화면과 결과 목록이 가로로 넘치지 않는다", async ({ page }) => {
  for (const [width, height] of [[1280, 900], [375, 812], [320, 640]]) {
    await page.setViewportSize({ width, height });
    await page.goto("/preview/plan-check");
    await expect(page.getByText("찾은 일정")).toBeVisible();
    await noHorizontalScroll(page);
    await page.getByRole("button", { name: "결과 바로 보기" }).click();
    await expect(page.getByRole("heading", { name: "10월 서울 여행", level: 1 })).toBeVisible();
    await noHorizontalScroll(page);
    await expect(card(page, "올리브영")).toBeInViewport({ ratio: 0.5 });
  }
});
