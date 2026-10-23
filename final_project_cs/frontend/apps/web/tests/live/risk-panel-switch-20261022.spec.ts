import { expect, test, type Page } from "@playwright/test";
import { mockServer, openRegistration, start } from "./helpers";

/**
 * `[2026-10-22 사용자 지시]` 관리 콘솔의 위험 점검 칸 스위치를 끄면(공개 읽기 `GET /v1/web/features` → `{risk_panel: false}`) 계획 확인 화면(등록 전 · 일정 수정)의
 * 점검 칸도 숨는다 — 여행 화면 칸(`trip.spec.ts`)과 같은 스위치. 계약: `wiki/external/rest-endpoints/web-trips.md` 「여행 화면 위험 점검 칸」.
 * 테스트용 mock 서버로 도는 자동 시험이다(화면 반응을 본다 — 실서버 확인 아님).
 */
const PLAN = "10/1 09:00 경복궁 관람";

async function checkedPlan(page: Page) {
  await start(page);
  await openRegistration(page);
  await page.getByLabel("나의 여행 계획").fill(PLAN);
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page).toHaveURL(/\/intakes\/[0-9a-f-]+$/);
  await expect(page.getByRole("button", { name: "여행 등록" })).toBeVisible();          // 확인이 끝났다 — 점검 칸이 나오는 때
}

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

// 항로 지킴이는 끈 장면(`guardian_off`)으로 둔다 — 켜져 있으면 「계획 확인하기」 앞에서 카드가 먼저 묻는다(`guardian-switch.spec.ts`). 점검 칸 스위치와는 따로 움직인다.
for (const [label, scenario] of [["점검 칸 값이 없는 응답(옛 서버)", { features: "guardian_off" }], ["스위치가 켜짐", { features: "guardian_off", riskPanel: "on" }]] as const) {
  test(`${label}이면 계획 확인 화면에 점검 칸이 그대로 있다`, async ({ page, request }) => {
    await mockServer(request).scenario(scenario);
    await checkedPlan(page);
    await expect(page.locator("[data-risk-panel]")).toHaveCount(1);
  });
}

test("운영자가 끄면 계획 확인 화면의 점검 칸이 없다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ features: "guardian_off", riskPanel: "off" });
  await checkedPlan(page);
  await expect(page.locator("[data-risk-panel]")).toHaveCount(0);
  expect((await server.received("GET", "/v1/web/features")).length).toBeGreaterThanOrEqual(1);
});
