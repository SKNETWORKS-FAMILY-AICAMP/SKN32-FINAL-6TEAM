import { expect, test, type Page } from "@playwright/test";
import { mockServer, openRegistration, PANES, start } from "./helpers";

/**
 * `[2026-10-25 사용자 지시 — ST4F-739]` 관리 콘솔의 「계획 담기 화면 보조 칸」 스위치(공개 읽기 `GET /v1/web/features` 의 `plan_input_extras`, 서버 기본 꺼짐)를 끄면
 * 계획 담기 화면에는 「직접 입력」 칸만 남는다 — 「파일 선택」 · 「계획 짜 주기 (테스트)」 · 「읽는 기준」 · 「여행 취향」 안내가 숨고, 고를 칸이 없으니 「보낼 칸」 표시도 없다.
 * 「이용 방법」(/help)의 그 칸 설명도 함께 숨는다(ST4F-717 D4). 계약: `wiki/external/rest-endpoints/web-trips.md` 「계획 담기 화면 보조 칸」.
 * 테스트용 mock 서버로 도는 자동 시험이다(화면 반응을 본다 — 실서버 확인 아님).
 */
const PLAN = "10/1 09:00 경복궁 관람";

const readingCriteria = (page: Page) => page.getByRole("heading", { name: "읽는 기준" });
const surveyLink = (page: Page) => page.getByRole("link", { name: "여행 취향 설문 하기" });

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

// 항로 지킴이는 끈 장면(`guardian_off`)으로 둔다 — 켜져 있으면 「계획 확인하기」 앞에서 카드가 먼저 묻는다(`guardian-switch.spec.ts`). 보조 칸 스위치와는 따로 움직인다.
test("운영자가 끄면 「직접 입력」 칸만 있고, 그 글은 그대로 보낸다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ features: "guardian_off", planInputExtras: "off" });
  await start(page);
  await openRegistration(page);
  await expect.poll(async () => (await server.received("GET", "/v1/web/features")).length).toBeGreaterThanOrEqual(1);
  await expect(PANES.text(page)).toBeVisible();
  await expect(PANES.text(page)).toHaveAttribute("aria-current", "true");
  await expect(PANES.files(page)).toHaveCount(0);
  await expect(PANES.plan(page)).toHaveCount(0);
  await expect(readingCriteria(page)).toHaveCount(0);
  await expect(surveyLink(page)).toHaveCount(0);
  await expect(page.getByText("보낼 칸")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "이렇게 적으면 잘 읽어요" })).toBeVisible();      // 입력 요령은 그대로

  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);
});

for (const [label, scenario] of [["보조 칸 값이 없는 응답(옛 서버)", { features: "guardian_off" }], ["스위치가 켜짐", { features: "guardian_off", planInputExtras: "on" }]] as const) {
  test(`${label}이면 네 칸이 다 있고 「보낼 칸」 표시가 붙는다`, async ({ page, request }) => {
    await mockServer(request).scenario(scenario);
    await start(page);
    await openRegistration(page);
    for (const pane of ["text", "files", "plan"] as const) await expect(PANES[pane](page)).toBeVisible();
    await expect(readingCriteria(page)).toBeVisible();
    await expect(surveyLink(page)).toBeVisible();
    await expect(PANES.text(page).getByText("보낼 칸")).toBeVisible();
  });
}

test("끈 동안은 「이용 방법」에도 그 칸들의 설명이 없다", async ({ page, request }) => {
  const server = mockServer(request);
  const fileQuestion = () => page.getByText("사진이나 파일로 된 계획도 올릴 수 있나요?");
  await server.scenario({ features: "guardian_off", planInputExtras: "off" });
  await start(page);
  await page.goto("/help?tab=faq");
  await expect(page.getByText("어떤 여행을 등록할 수 있나요?")).toBeVisible();
  await expect(fileQuestion()).toHaveCount(0);
  await expect(page.getByText("일정을 대신 짜 주기도 하나요?")).toHaveCount(0);

  await server.scenario({ planInputExtras: "on" });
  await page.reload();
  await expect(fileQuestion()).toBeVisible();
});
