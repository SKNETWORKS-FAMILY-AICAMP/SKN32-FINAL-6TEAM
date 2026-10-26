import { expect, test } from "@playwright/test";
import { checkPlan, mockServer, start } from "./helpers";

/**
 * ★`[2026-10-26 사용자 보고 — 「이거 이렇게 완료가 안 되었는데 다음 화면 뜨는 버그」 · 모바일 폭 스크린숏]` x600 접수가 읽기 실패(`fatal` · `reading_model_failed`)로 끝났는데,
 * 질문에 답하던 고객의 읽기 화면에 막대 「일정 읽기 8/9줄」인 채로 「✓ 계획을 다 읽었어요」 · 「이제 자동으로 넘어가지 않아요.」 · 켜진 「읽어 온 계획 확인하기」가 떴다.
 * 실패한 읽기는 「다 읽었어요」가 아니다 — 실패 화면(「이 계획을 읽지 못했어요」 · `fatal.detail` · 「다시 올리기」)이 떠야 한다(web-intakes 125 · 129행).
 * 테스트용 mock 서버로 도는 자동 시험이다(화면 반응을 본다 — 실서버 확인 아님).
 */
const PLAN = "10/1 09:00 경복궁 관람";
const HOLD = 999;

test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

// 사용자 화면의 「이제 자동으로 넘어가지 않아요.」는 실패 뒤 뜬 「다 읽었어요」(done)에서 「자동으로 넘어가지 않기」를 누른 결과다 — 고친 뒤에는 done 자체가 안 뜬다.
for (const how of ["질문에 답하던 중", "질문을 건드리지 않은 채"] as const) {
  test(`읽기가 실패(fatal)로 끝나면 ${how}여도 「계획을 다 읽었어요」 · 「읽어 온 계획 확인하기」 없이 실패를 말한다 (모바일 폭)`, async ({ page, request }) => {
    const server = mockServer(request);
    await server.scenario({ questions: "two", readingPolls: HOLD, intake: "fatal" });
    // 실패 뒤 「다 읽었어요」가 5초 막대 동안만 잠깐 떴다가 실패 화면으로 바뀌어도 놓치지 않게, 화면에 한 번이라도 나온 적이 있는지 처음부터 센다.
    await page.addInitScript(() => {
      const seen = { done: false, button: false };
      (window as unknown as { __readingSeen: typeof seen }).__readingSeen = seen;
      new MutationObserver(() => {
        const text = document.body?.innerText ?? "";
        if (text.includes("계획을 다 읽었어요")) seen.done = true;
        if (Array.from(document.querySelectorAll("button")).some((button) => button.textContent?.includes("읽어 온 계획 확인하기"))) seen.button = true;
      }).observe(document, { childList: true, subtree: true, characterData: true });
    });
    await start(page);
    await page.goto("/trips/new");
    await page.getByLabel("나의 여행 계획").fill(PLAN);
    await checkPlan(page);
    await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);
    const pager = page.getByRole("region", { name: /^질문 \d개$/ });
    await expect(pager.getByRole("heading", { name: "누구와 함께 떠나나요?" })).toBeVisible();
    await expect(page.getByRole("button", { name: "계획 읽는 중…" })).toHaveAttribute("aria-disabled", "true");
    if (how !== "질문을 건드리지 않은 채") await pager.getByRole("button", { name: "친구", exact: true }).click();

    await server.scenario({ readingPolls: 0 });

    await expect(page.getByRole("heading", { name: "이 계획을 읽지 못했어요" })).toBeVisible();
    await expect(page.getByRole("alert").filter({ hasText: "사진에서 글자를 찾지 못했어요" })).toBeVisible();     // fatal.detail 그대로
    await expect(page.getByRole("link", { name: "다시 올리기" })).toBeVisible();
    await expect(page.getByText("계획을 다 읽었어요")).toHaveCount(0);
    await expect(page.getByText("이제 자동으로 넘어가지 않아요.")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "자동으로 넘어가지 않기" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "읽어 온 계획 확인하기" })).toHaveCount(0);
    expect(await page.evaluate(() => (window as unknown as { __readingSeen: { done: boolean; button: boolean } }).__readingSeen)).toEqual({ done: false, button: false });
    await page.screenshot({ path: test.info().outputPath(`reading-failed-${how === "질문에 답하던 중" ? "touched" : "untouched"}.png`), fullPage: false });
  });
}
