import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { mockServer, start } from "./helpers";

/**
 * 계획 확인 화면(`/intakes/[id]`) 시험이 함께 쓰는 도구 — 접수 번호 · 카드/핀/시트 찾기 · 서버 응답 고쳐 쓰기 · 이미 읽힌 접수 열기.
 * mock 서버(`stub-server.mjs`)의 `review: "on"` + `board: "rich"` 장면: 장소 셋(경복궁 관람 · 올리브영(확인 필요) · 광장시장)과 이동 둘(지하철 3호선 · 1호선).
 */
export const INTAKE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
export const INTAKE_READ = `**/v1/web/trip-intakes/${INTAKE}`;

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- 서버 응답을 시험에서 고쳐 쓰는 자리라 모양을 고정하지 않는다
export type Json = Record<string, any>;

export const card = (page: Page, title: string) => page.getByRole("article", { name: title, exact: true });
/** 카드 머리의 제목 단추(펼침·접힘). */
export const head = (page: Page, title: string) => card(page, title).getByRole("heading").getByRole("button");
/** 지도의 핀 — Leaflet 이 만든 요소이고 `title` 이 「1. 경복궁 관람 · 2026-10-01 09:00」 꼴이다. `aria-pressed` 는 이 바깥 요소에 붙는다. */
export const pin = (page: Page, label: string) => page.locator(`.leaflet-marker-icon[title^="${label}"]`);
export const sheet = (page: Page) => page.getByRole("region", { name: /장소·운영시간 확인|계획 확인|수정안|등록 완료/ });
export const toast = (page: Page, text: string) => page.getByRole("status").filter({ hasText: text });
/** 머리의 「! 2」 표시(확인이 필요한 곳) — 결과가 그려졌다는 신호로도 쓴다. */
export const needsBadge = (page: Page) => page.getByRole("button", { name: /^확인 필요 \d+곳$/ });
export const changedBadge = (page: Page) => page.getByRole("button", { name: /^바뀐 일정 \d+곳$/ });

/** 접수 조회(GET)의 mock 서버 응답을 `change` 로 고쳐서 돌려 준다 — 쓰기 요청은 그대로 통과. 화면을 열기 전에 건다. */
export async function patchIntake(page: Page, change: (view: Json) => void) {
  await page.route(INTAKE_READ, async (route) => {
    if (route.request().method() !== "GET") { await route.continue(); return; }
    const response = await route.fetch();
    const view = await response.json();
    change(view);
    await route.fulfill({ response, json: view });
  });
}

/** 이미 읽힌 접수를 바로 연다(읽는 중 화면을 건너뛴다). */
export async function openFinished(page: Page, request: APIRequestContext, patch?: (view: Json) => void, scenario: Json = {}, settle = true) {
  const server = mockServer(request);
  await server.scenario({ review: "on", board: "rich", readingPolls: 0, ...scenario });
  if (patch) await patchIntake(page, patch);
  await start(page);
  await page.goto(`/intakes/${INTAKE}`);
  await expect(needsBadge(page)).toBeVisible();
  if (settle) await mapSettled(page);                                                                     // false: a test of what the map does right as it first shows (the pulse of the first pin)
  return server;
}

/**
 * The map is still flying to its first view for about a second after the check ends. A pin pressed while it moves loses the press (the pin leaves from under the pointer between the press and the release, so the
 * release lands on the map): wait until the first pin has stood still for a few samples before a test presses anything on the map.
 */
export async function mapSettled(page: Page) {
  const body = page.locator("[data-pin-body]").first();
  let last = "";
  let still = 0;
  await expect.poll(async () => {
    const box = await body.boundingBox().catch(() => null);
    const now = box ? `${Math.round(box.x)},${Math.round(box.y)}` : "";
    still = now === last ? still + 1 : 0;
    last = now;
    return still;
  }, { intervals: [100], timeout: 10_000 }).toBeGreaterThanOrEqual(5);
}
