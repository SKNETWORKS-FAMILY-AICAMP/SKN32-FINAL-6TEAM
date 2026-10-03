import { expect, test, type Page } from "@playwright/test";
import { start, stub, TRIP_ID } from "./helpers";

test.beforeEach(async ({ page, request }) => {
  await stub(request).reset();
  await start(page);
});

async function openTrip(page: Page) {
  await page.goto(`/trips/${TRIP_ID}`, { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: "나의 여행", exact: true })).toBeVisible();
}

async function changingTrip(page: Page) {
  const state = { version: 1, fail: false, trips: 0, notices: 0, proposals: 0 };
  await page.route(`**/v1/web/trips/${TRIP_ID}`, async (route) => {
    state.trips += 1;
    if (state.fail) {
      await route.fulfill({ status: 500, json: { error: { code: "trip_read_failed", message: "internal detail" } } });
      return;
    }
    const body = await (await route.fetch()).json();
    if (state.version > 1) {
      body.version = state.version;
      body.items[0].title = "새 아침 식당";
      body.warnings = [{ code: "changed", reason: "변경된 여행 경고" }];
      body.history.push({ version: state.version, reason: "새 변경 이력", at: "2026-10-01T00:00:00Z" });
    }
    await route.fulfill({ json: body });
  });
  await page.route("**/notices", async (route) => {
    state.notices += 1;
    await route.fulfill({ json: { notices: [{ key: `n-${state.version}`, type: "change_notice",
      text: `일정 ${state.version}판 알림`, version: state.version, delivery: "sent", at: "2026-10-01T00:00:00Z" }] } });
  });
  await page.route("**/proposals", async (route) => { state.proposals += 1; await route.continue(); });
  return state;
}

test("알림·제안을 1분마다 읽고 변경 때 일정·지도·경고·이력을 함께 갱신하며 입력을 보존한다", async ({ page }) => {
  const state = await changingTrip(page);
  await page.clock.install();
  await openTrip(page);
  expect([state.notices, state.proposals]).toEqual([1, 1]);
  const initialTrips = state.trips;
  await page.getByRole("button", { name: "채팅", exact: true }).click();
  const input = page.getByPlaceholder("일정에 대해 궁금한 점을 입력하세요");
  await input.fill("작성 중인 질문");
  state.version = 2;
  await page.clock.fastForward(30_000);
  expect([state.notices, state.proposals, state.trips]).toEqual([1, 1, initialTrips]);
  await page.clock.fastForward(30_000);
  await expect(page.getByText("변경된 여행 경고")).toBeVisible();
  expect([state.notices, state.proposals, state.trips]).toEqual([2, 2, initialTrips + 1]);
  await expect(input).toHaveValue("작성 중인 질문");
  await page.getByRole("button", { name: "일정", exact: true }).click();
  await expect(page.locator("#trip-pane-schedule").getByText("새 아침 식당")).toBeVisible();
  await page.getByRole("button", { name: "방문 순서", exact: true }).click();
  await expect(page.locator("#trip-pane-map").getByRole("button", { name: "1. 새 아침 식당" })).toBeVisible();
  const history = page.locator("details").filter({ hasText: "변경 이력" });
  await history.locator("summary").click();
  await expect(history).toContainText("새 변경 이력");
  await page.clock.fastForward(60_000);
  await expect.poll(() => state.notices).toBe(3);
  expect(state.proposals).toBe(3);
  expect(state.trips).toBe(initialTrips + 1); // 같은 알림이면 여행을 반복 조회하지 않는다.
});

test("알림 후 여행 조회가 실패해도 기존 화면·초안을 보존하고 다음 1분 조회에서 복구한다", async ({ page }) => {
  const state = await changingTrip(page);
  await page.clock.install();
  await openTrip(page);
  await page.getByRole("button", { name: "채팅", exact: true }).click();
  const input = page.getByPlaceholder("일정에 대해 궁금한 점을 입력하세요");
  await input.fill("보존할 질문");
  state.version = 2;
  state.fail = true;
  await page.clock.fastForward(60_000);
  await expect(page.locator("main").getByRole("alert").filter({ hasText: "마지막으로 확인한 내용" })).toBeVisible();
  await expect(input).toHaveValue("보존할 질문");
  const attempts = state.trips;
  state.fail = false;
  await page.clock.fastForward(60_000);
  await expect(page.getByText("변경된 여행 경고")).toBeVisible();
  await expect(page.locator("main").getByRole("alert")).toHaveCount(0);
  await expect(input).toHaveValue("보존할 질문");
  expect(state.trips).toBe(attempts + 1);
});

test("화면 진입 직후의 첫 알림도 여행 데이터와 동기화한다", async ({ page }) => {
  const state = await changingTrip(page);
  await page.route("**/notices", async (route) => {
    state.version = 2;
    await route.fallback();
  });
  await openTrip(page);
  await expect(page.locator("#trip-pane-schedule").getByText("새 아침 식당")).toBeVisible();
  expect(state.trips).toBeGreaterThanOrEqual(2);
});

for (const failure of ["network", "server", "refresh"] as const) {
  test(`채팅 ${failure} 실패는 공통 안내·진단 기록을 남기고 다시 보내기는 새 요청이다`, async ({ page, request }) => {
    const diagnostics: Record<string, unknown>[] = [];
    page.on("console", async (message) => {
      if (message.type() === "error" && message.text().startsWith("[tripilot.chat]")) {
        diagnostics.push(await message.args()[1].jsonValue());
      }
    });
    await openTrip(page);
    const sent: { request_id: string; message: string }[] = [];
    await page.route("**/messages", async (route) => {
      sent.push(route.request().postDataJSON());
      if (sent.length === 1 && failure !== "refresh") {
        if (failure === "network") await route.abort("failed");
        else await route.fulfill({ status: 500, json: { error: { code: "chat_failed", message: "비공개 서버 오류 원문" } } });
        return;
      }
      await route.continue();
    });
    if (failure === "refresh") {
      await page.route(`**/v1/web/trips/${TRIP_ID}`, async (route) => {
        await route.fulfill({ status: 500, json: { error: { code: "trip_read_failed", message: "비공개 서버 오류 원문" } } });
      }, { times: 1 });
    }
    await page.getByRole("button", { name: "채팅", exact: true }).click();
    const input = page.getByPlaceholder("일정에 대해 궁금한 점을 입력하세요");
    await input.fill("식당이 휴무예요");
    await page.getByRole("button", { name: "메시지 전송" }).click();
    const alert = page.locator("main").getByRole("alert");
    await expect(alert).toContainText("서버 연결이 불안정해요. 잠시 후 다시 시도해 주세요.");
    await expect(alert).not.toContainText("비공개");
    await expect(input).toHaveValue("식당이 휴무예요");
    await expect.poll(() => diagnostics.length).toBe(1);
    expect(diagnostics[0]).toEqual({
      requestId: sent[0].request_id, stage: failure === "refresh" ? "refresh_trip" : "send_message",
      at: expect.any(String), code: failure === "network" ? "network" : failure === "refresh" ? "trip_read_failed" : "chat_failed",
      status: failure === "network" ? undefined : 500,
    });
    expect(JSON.stringify(diagnostics)).not.toMatch(/acop_u_known|식당이 휴무예요|비공개/);
    await page.getByRole("button", { name: "다시 보내기" }).click();
    await expect(page.locator("article[data-role=assistant]").last()).toContainText("서버 답: 식당이 휴무예요");
    await expect(input).toHaveValue("");
    expect(sent).toHaveLength(2);
    expect(sent[1].request_id).not.toBe(sent[0].request_id);
    expect(sent[1].message).toBe(sent[0].message);
    expect(await stub(request).received("POST", "/messages")).toHaveLength(failure === "refresh" ? 2 : 1);
  });
}

for (const error of [
  { code: "usage_limit", status: 429 },
  { code: "service_daily_cap", status: 503 },
]) {
  test(`채팅 ${error.code} 제한은 서버 장애로 바꾸지 않고 재시도 가능 시간을 안내한다`, async ({ page }) => {
    await openTrip(page);
    await page.route("**/messages", (route) => route.fulfill({ status: error.status,
      json: { error: { code: error.code, message: "오늘 사용량을 다 썼어요.", retry_after_seconds: 120 } } }));
    await page.getByRole("button", { name: "채팅", exact: true }).click();
    await page.getByRole("button", { name: "하루 요약" }).click();
    await expect(page.locator("main").getByRole("alert")).toContainText("오늘 사용량을 다 썼어요. (2분 뒤에 다시 할 수 있어요.)");
    await expect(page.locator("main").getByRole("alert")).not.toContainText("서버 연결이 불안정");
  });
}
