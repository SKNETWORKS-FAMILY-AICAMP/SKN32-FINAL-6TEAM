import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { beforeTheTrip, mockServer, noHorizontalScroll, openPane, start, STUB, TRIP_ID, tripScreen } from "./helpers";
import { INTAKE, INTAKE_READ, openFinished, type Json } from "./plan-check-kit";

/**
 * `[2026-10-19 사용자 결정 — 못 찾은 장소는 후보 보이고 묻기 + 직접 고르기]` (`wiki/external/rest-endpoints/web-intakes.md` 「장소를 못 찾았을 때」)
 * ① 계획 확인 화면: 서버가 장소를 못 찾은 줄(`prefill.questions[]` `kind: place_not_found`)은 그 일정 카드에 질문 칸이 붙는다 — 서버 문장 그대로 · 후보(있으면) · 「직접 고르기」 · 「장소 없이 두기」.
 *    「직접 고르기」는 새 화면 없이 그 일정의 장소 바꾸기를 열고 검색 칸에 바로 쓸 수 있다.
 * ② 여행 화면 채팅: 장소를 못 찾은 거절 답의 `pick` — 「직접 고르기」를 누르면 「일정 수정」과 같은 수정 모드로 넘어가 그 일정의 장소 검색(`change`) / 미리 채운 일정 추가 칸(`add`)이 열린다.
 * mock 서버의 화면 반응을 확인하는 자동 시험이다(실서버 아님).
 */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const unfoundCard = (page: Page) => page.locator('[data-unfound="0-1"]');
const placeEdits = async (request: APIRequestContext) => (await mockServer(request).received("POST", "/edits"))
  .flatMap((entry) => ((entry.body?.edits ?? []) as { field: string; value: unknown }[]).filter((edit) => edit.field === "items[1].place"));

test("후보가 둘인 못 찾은 줄: 카드에 서버 문장과 후보 둘이 보이고, 후보를 누르면 그 장소 그대로 보낸다", async ({ page, request }) => {
  await openFinished(page, request, undefined, { unfound: "on" });
  const box = unfoundCard(page);
  await expect(box).toBeVisible();
  await expect(box).toContainText("「을지로 그 집」을 지도에서 찾지 못했어요 — 후보에서 고르거나 직접 골라 주세요");
  await expect(box.getByRole("listitem")).toHaveCount(2);
  await expect(box.getByRole("button", { name: "올리브영 광화문점으로 정하기" })).toBeVisible();
  await expect(box.getByRole("button", { name: "직접 고르기" })).toBeVisible();
  await expect(box.getByRole("button", { name: "장소 없이 두기" })).toBeVisible();
  // 카드에 실린 질문은 목록 위 안내에 또 나오지 않는다
  await expect(page.locator("[data-prefill-note]")).toHaveCount(0);
  await box.getByRole("button", { name: "올리브영 광화문점으로 정하기" }).click();
  await expect.poll(async () => (await placeEdits(request)).length).toBe(1);
  expect((await placeEdits(request))[0].value).toMatchObject({ name: "올리브영 광화문점", latitude: 37.5717, longitude: 126.9791, source: "kakao" });
  // 장소가 정해지면 더 묻지 않는다
  await expect(unfoundCard(page)).toHaveCount(0);
});

test("후보가 없고 조회가 막혔던 줄: 후보 칸 없이 단추 둘, 「장소 없이 두기」는 장소 없음으로 보낸다", async ({ page, request }) => {
  await openFinished(page, request, undefined, { unfound: "blocked", candidateNotes: ["no_same_kind"] });
  const box = unfoundCard(page);
  await expect(box).toContainText("장소 조회가 막혀 다시 찾아봤지만 「을지로 그 집」을 찾지 못했어요");
  await expect(box).toHaveAttribute("data-blocked", "true");
  await expect(box.getByRole("status")).toHaveCount(0);                    // 후보를 다 받았다(찾는 중이 아니다)
  await expect(box.getByRole("listitem")).toHaveCount(0);
  await expect(box.getByRole("button")).toHaveText(["직접 고르기", "장소 없이 두기"]);
  await box.getByRole("button", { name: "장소 없이 두기" }).click();
  await expect.poll(async () => (await placeEdits(request)).length).toBe(1);
  expect((await placeEdits(request))[0].value).toEqual({ none: true });
  await expect(unfoundCard(page)).toHaveCount(0);
});

test("「직접 고르기」는 화면을 바꾸지 않고 그 일정의 장소 바꾸기를 열어 검색 칸에 바로 쓰게 한다", async ({ page, request }) => {
  await openFinished(page, request, undefined, { unfound: "on" });
  const url = page.url();
  await unfoundCard(page).getByRole("button", { name: "직접 고르기" }).click();
  await expect(page.getByRole("heading", { name: "을지로 그 집 바꾸기" })).toBeVisible();
  const field = page.getByRole("searchbox", { name: "장소 검색" });
  await expect(field).toBeFocused();
  expect(page.url()).toBe(url);
  await page.keyboard.type("올리브영");
  await expect(page.getByText("‘올리브영’ 검색 결과 1곳")).toBeVisible();
});

test("375px · 320px 에서 못 찾은 장소 카드가 가로로 넘치지 않는다", async ({ page, request }) => {
  for (const [width, height] of [[375, 812], [320, 640]]) {
    await page.setViewportSize({ width, height });
    await openFinished(page, request, undefined, { unfound: "on" });
    await expect(unfoundCard(page).getByRole("listitem")).toHaveCount(2);
    await noHorizontalScroll(page);
  }
});

/** 수정 모드(`POST …/reopen`): mock 서버의 접수를 「여행을 다시 연 접수」처럼 고쳐 쓴다 — 줄마다 그 줄을 연 여행 일정 id(`evidence.item_id`)를 단다. 광장시장 줄(0-2) = 여행의 점심 식당(i-c). */
function asReopened(view: Json) {
  view.reopen = { trip_id: TRIP_ID, version: 1, frozen_item_ids: [], frozen: [] };
  const trip = ["i-a", "i-b", "i-c"];
  for (const item of view.sources?.[0]?.items ?? []) {
    for (const field of Object.values(item.fields ?? {}) as Json[]) field.evidence = { ...field.evidence, source: "trip", item_id: trip[item.index] };
  }
  return view;
}

async function openTripChat(page: Page, request: APIRequestContext, chat: "pick_change" | "pick_add") {
  await mockServer(request).scenario({ review: "on", board: "rich", readingPolls: 0, chat });
  await start(page);
  await beforeTheTrip(page);
  const response = await request.get(`${STUB}/v1/web/trip-intakes/${INTAKE}`, { headers: { "X-User-Key": "acop_u_known" } });
  const reopened = asReopened(await response.json());
  await page.route(`**/v1/web/trips/${TRIP_ID}/reopen`, (route) => route.fulfill({ json: reopened }));
  await page.route(INTAKE_READ, async (route) => {
    if (route.request().method() !== "GET") { await route.continue(); return; }
    const fresh = await route.fetch();
    await route.fulfill({ response: fresh, json: asReopened(await fresh.json()) });
  });
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(tripScreen(page)).toBeVisible();
  await openPane(page, "채팅");
  await page.locator("#trip-chat-message").fill(chat === "pick_add" ? "1일차 저녁 7시에 민수네 넣어 줘" : "점심 식당을 민수네로 바꿔 줘");
  await page.getByRole("button", { name: "메시지 전송" }).click();
  const log = page.getByRole("log", { name: "여행 대화 이력" });
  await expect(log).toContainText("「민수네」를 지도에서 찾지 못해 일정은 바꾸지 않았어요");
  await expect(log).toHaveAttribute("aria-busy", "false");
  return log;
}

test("채팅 답 pick change: 「직접 고르기」는 수정 모드로 넘어가 그 일정의 장소 검색을 「민수네」로 연다 — 새로 고쳐도 단추가 남는다", async ({ page, request }) => {
  const log = await openTripChat(page, request, "pick_change");
  // 서버의 대화 기록(`turns[].reply.pick`)에서도 단추가 다시 나온다
  await page.evaluate(() => sessionStorage.clear());
  await page.reload();
  await openPane(page, "채팅");
  await log.getByRole("button", { name: "직접 고르기" }).click();
  await expect(page.getByRole("heading", { name: "광장시장 바꾸기" })).toBeVisible();
  const field = page.getByRole("searchbox", { name: "장소 검색" });
  await expect(field).toHaveValue("민수네");
  await expect(field).toBeFocused();
  await expect(page.getByText("‘민수네’ 검색 결과 1곳")).toBeVisible();
});

test("채팅 답 pick add: 「직접 고르기」는 수정 모드의 일정 추가 칸을 채팅 값으로 채워 연다", async ({ page, request }) => {
  const log = await openTripChat(page, request, "pick_add");
  await log.getByRole("button", { name: "직접 고르기" }).click();
  const screen = page.getByRole("region", { name: "일정 추가 화면" });
  await expect(screen).toBeVisible();
  const field = page.getByRole("searchbox", { name: "장소 검색" });
  await expect(field).toHaveValue("민수네");
  // 검색 결과에서 장소를 고르면 채팅 값이 든 칸이 보인다(이름은 고객이 말한 「민수네」 그대로)
  await screen.getByRole("button", { name: /올리브영 명동 플래그십/ }).click();
  await expect(screen.getByLabel("일정 이름")).toHaveValue("민수네");
  await expect(screen.getByLabel("날짜")).toHaveValue("2026-10-01");
  await expect(screen.getByLabel("시작")).toHaveValue("19:00");
  await expect(screen.getByLabel("끝")).toHaveValue("20:00");
  await expect(screen.getByLabel("일정 종류")).toHaveValue("dining");
  await screen.getByRole("button", { name: "일정에 추가" }).click();
  await expect.poll(async () => (await mockServer(request).received("POST", "/edits")).length).toBe(1);
  const [sent] = await mockServer(request).received("POST", "/edits");
  const fields = Object.fromEntries(((sent.body?.edits ?? []) as { field: string; value: unknown }[]).map((edit) => [edit.field.replace(/^items\[\d+\]\./, ""), edit.value]));
  expect(fields).toMatchObject({ title: "민수네", date: "2026-10-01", starts_at: "19:00", ends_at: "20:00", kind: "dining" });
});
