import { expect, test } from "@playwright/test";
import { mockServer } from "./helpers";
import { openFinished } from "./plan-check-kit";

/**
 * `[2026-10-14 x600 실서버 확인]` 시간 고치기 창이 열려 있는 동안 오른쪽 아래 둥근 단추(「여행 등록」 · 「다시 제출」 · 수정 모드의 「완료」)를 숨긴다.
 * 창의 ✓ 「적용」이 아래쪽에 오면 같은 초록 ✓ 인 둥근 단추가 그 위를 덮어, 「적용」을 누른 손님이 「완료」를 눌렀다(수정 모드가 아무것도 쓰지 않고 닫혔다).
 * mock 서버 시험이다 — 화면 반응을 본다.
 */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const finish = (page: import("@playwright/test").Page) => page.getByRole("button", { name: /^(여행 등록|다시 제출|완료)$/ });

test("시간 고치기 창을 여는 동안 둥근 단추가 사라지고, 「적용」으로 닫으면 「다시 제출」로 돌아온다", async ({ page, request }) => {
  await openFinished(page, request);
  await expect(finish(page)).toHaveCount(1);
  await page.getByRole("button", { name: /^경복궁 관람 시간 고치기/ }).click();
  const form = page.getByRole("form", { name: "경복궁 관람 시간 고치기" });
  await expect(form).toBeVisible();
  await expect(finish(page)).toHaveCount(0);                                                       // ★창이 열린 동안은 없다 — 「적용」을 덮지 않는다
  await form.getByRole("button", { name: "+5분" }).click();
  await form.getByRole("button", { name: "적용", exact: true }).click();
  await expect(form).toHaveCount(0);
  await expect(page.getByRole("button", { name: "다시 제출", exact: true })).toBeVisible();        // 닫으면 다시 나온다
});

test("시간 고치기 창을 「취소」로 닫아도 둥근 단추가 돌아온다", async ({ page, request }) => {
  await openFinished(page, request);
  await page.getByRole("button", { name: /^경복궁 관람 시간 고치기/ }).click();
  const form = page.getByRole("form", { name: "경복궁 관람 시간 고치기" });
  await expect(finish(page)).toHaveCount(0);
  await form.getByRole("button", { name: "취소", exact: true }).click();
  await expect(form).toHaveCount(0);
  await expect(finish(page)).toHaveCount(1);
});
