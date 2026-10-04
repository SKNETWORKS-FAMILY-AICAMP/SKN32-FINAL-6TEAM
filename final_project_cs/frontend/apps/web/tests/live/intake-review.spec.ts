import { expect, test, type Page } from "@playwright/test";
import { mockServer, start, TRIP_ID } from "./helpers";

/**
 * `[2026-10-03 사용자 결정]` 옛 목록형 확인 화면(카드를 펼쳐 고치는 화면, 「읽은 일정이 없어요 — 대신 짜 드릴까요?」 칸, 「읽은 원문 전체 보기」)은
 * 없앴고, 일정 짜기는 등록 화면의 세 번째 칸(「계획 짜 주기 (테스트)」)으로 옮겼다. 이 파일은 접수 화면(`/intakes/[id]`)에서
 * 「서버가 글을 읽었는데 일정이 하나도 없는」 경우가 짧은 안내 하나로 끝나는지, 그리고 그 안내가 일정을 모두 지운 경우와 섞이지 않는지 본다.
 * (옛 화면의 카드 편집 시험 6건은 옛 화면과 함께 지웠다 — 새 결과 화면의 수정·삭제는 `flow.spec.ts` 와 `plan-check-screen.spec.ts` 가 본다.)
 * 테스트용 모방 서버로 도는 자동 시험이다(실제 서버 아님).
 */
const ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const path = `**/v1/web/trip-intakes/${ID}`;

test.beforeEach(async ({ request }) => {
  await mockServer(request).reset();
  await mockServer(request).scenario({ readingPolls: 0 });
});

/** Change the intake the server answers with (the mock server has the two shapes it has; the rest is patched here, as a server would answer). */
async function patchIntake(page: Page, change: (view: Record<string, any>) => void) { // eslint-disable-line @typescript-eslint/no-explicit-any
  await page.route(path, async (route) => {
    const response = await route.fetch();
    const view = await response.json();
    change(view);
    await route.fulfill({ response, json: view });
  });
}

test("서버가 글을 읽었는데 일정이 없고 짜 달라는 말도 없으면, 짧은 안내와 등록 화면으로 가는 링크 하나만 나온다", async ({ page, request }) => {
  await mockServer(request).scenario({ intake: "empty_plan" });
  await patchIntake(page, (view) => { view.check.plan.requested = false; });
  await start(page);
  await page.goto(`/intakes/${ID}`);
  await expect(page.getByRole("heading", { name: "이 글에서는 일정을 찾지 못했어요" })).toBeVisible();
  await expect(page.getByText("읽은 일정이 없어요. 원문을 확인해 다시 올리거나, 등록 화면의 「계획 짜 주기」를 써 보세요.")).toBeVisible();
  const main = page.locator("#main-content");
  await expect(main.getByRole("link")).toHaveCount(1);
  await expect(main.getByRole("link", { name: "등록 화면으로" })).toHaveAttribute("href", "/trips/new");
  // 옛 화면에 있던 것들은 없다
  await expect(page.getByRole("button", { name: /이 조건으로 짜서 등록|여행 등록|확인 결과 새로고침/ })).toHaveCount(0);
  await expect(page.getByText("읽은 원문 전체 보기")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "여행 계획 살펴보기" })).toHaveCount(0);
});

test("짜 달라는 요청은 읽었지만 일정이 없으면, 안내가 등록 화면의 「계획 짜 주기」로 첫날·일수·인원을 고르라고 말한다", async ({ page, request }) => {
  await mockServer(request).scenario({ intake: "empty_plan" });            // 모방 서버의 이 시나리오는 plan.requested: true
  await start(page);
  await page.goto(`/intakes/${ID}`);
  await expect(page.getByRole("heading", { name: "이 글에서는 일정을 찾지 못했어요" })).toBeVisible();
  await expect(page.getByText("글에서 일정을 짜 달라는 요청은 읽었어요", { exact: false })).toContainText("등록 화면의 「계획 짜 주기」에서 첫날 · 일수 · 인원을 골라 짜 보세요");
  await page.getByRole("link", { name: "등록 화면으로" }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(page.getByRole("region", { name: "계획 짜 주기 (테스트)" })).toBeVisible();
});

test("일정이 읽혔는데 글에 짜 달라는 말도 있었다면, 읽은 일정의 결과 화면에 그 사실을 한 줄로 알린다", async ({ page }) => {
  await patchIntake(page, (view) => { view.check.plan.requested = true; });
  await start(page);
  await page.goto(`/intakes/${ID}`);
  await expect(page.getByRole("article", { name: "경복궁 관람" })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "글에 일정을 짜 달라는 말도 있었어요" })).toContainText("등록 화면의 「계획 짜 주기」");
  await expect(page.getByRole("heading", { name: "이 글에서는 일정을 찾지 못했어요" })).toHaveCount(0);
});

test("이미 여행으로 등록한 접수에 읽은 일정이 없으면(짜서 등록한 접수) 안내 대신 그 여행으로 가는 링크를 준다", async ({ page }) => {
  await patchIntake(page, (view) => { view.status = "confirmed"; view.trip_id = TRIP_ID; view.sources[0].items = []; });
  await start(page);
  await page.goto(`/intakes/${ID}`);
  await expect(page.getByRole("heading", { name: "이 접수는 여행으로 등록했어요" })).toBeVisible();
  await expect(page.getByRole("link", { name: "여행 보기" })).toHaveAttribute("href", `/trips/${TRIP_ID}`);
  await expect(page.getByRole("heading", { name: "이 글에서는 일정을 찾지 못했어요" })).toHaveCount(0);
});

test("고객이 일정을 모두 지워도 「읽은 일정이 없어요」 안내로 바뀌지 않는다 — 결과 화면이 「남은 일정이 없어요」를 말하고 그대로 남는다", async ({ page }) => {
  // 서버는 지운 일정을 읽은 일정에 남기되 removed 표시를 한다(`rows()` 가 그 표시를 걸러 낸다) — 모방 서버는 그 표시를 안 하므로 여기서 대신 한다.
  let gone = false;
  await page.route(new RegExp(`/v1/web/trip-intakes/${ID}(/edits)?$`), async (route) => {
    if (route.request().url().endsWith("/edits")) gone = true;
    const response = await route.fetch();
    const view = await response.json();
    if (gone) view.sources[0].items[0].fields.removed = { value: true, method: "customer", evidence: {}, needs_review: false, note: null };
    await route.fulfill({ response, json: view });
  });
  await start(page);
  await page.goto(`/intakes/${ID}`);
  await page.getByRole("button", { name: "경복궁 관람 삭제" }).click();
  await page.getByRole("button", { name: "다시 제출" }).click();                                     // 삭제는 다시 제출할 때 서버로 간다
  await expect(page.getByText("남은 일정이 없어요")).toBeVisible();
  await expect(page.getByRole("heading", { name: "이 글에서는 일정을 찾지 못했어요" })).toHaveCount(0);
});
