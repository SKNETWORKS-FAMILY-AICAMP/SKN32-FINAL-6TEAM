import { expect, test, type Page } from "@playwright/test";
import type { IntakeView } from "../../src/lib/live/intake";
import { start, stub, TRIP_ID } from "./helpers";

test.beforeEach(async ({ request }) => { await stub(request).reset(); });

async function menuLink(page: Page, name: RegExp) {
  await page.getByRole("button", { name: "메뉴", exact: true }).first().click();
  await page.getByRole("dialog", { name: "메뉴" }).getByRole("link", { name }).click();
}

test("저장소 차단 중에도 계획 접수와 조회는 같은 키를 쓰고 보관 경고와 키를 표시한다", async ({ page, request }) => {
  await start(page, null);
  await page.addInitScript(() => {
    for (const method of ["getItem", "setItem", "removeItem"] as const) {
      const original = Storage.prototype[method];
      Storage.prototype[method] = function (key: string, value?: string) {
        if (key.startsWith("tripilot.web.user-key")) throw new DOMException("blocked", "SecurityError");
        return Reflect.apply(original, this, [key, value]);
      };
    }
  });
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill("10/1 09:00 경복궁 관람");
  await page.getByRole("button", { name: "계획 확인하기" }).click();
  await expect(page.getByRole("heading", { name: "경복궁 관람" })).toBeVisible();
  const notice = page.getByRole("status").filter({ hasText: "내 여행 열쇠를 따로 보관해 주세요" });
  await expect(notice.getByRole("alert")).toContainText("브라우저에 키를 저장하지 못했어요");
  await expect(notice.getByRole("textbox")).toHaveValue("acop_u_stub_1");
  await notice.getByRole("button", { name: "따로 보관했어요" }).click();
  await page.getByRole("button", { name: "등록하고 관리 시작" }).click();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));
  await expect(page.getByRole("heading", { name: "나의 여행", exact: true })).toBeVisible();
  const log = await stub(request).log();
  expect(log.filter((entry) => entry.path === "/v1/web/session")).toHaveLength(1);
  expect(log.filter((entry) => entry.path !== "/v1/web/session").every((entry) => entry.key === "acop_u_stub_1")).toBe(true);
});

test("다른 키로 전환한 뒤 조회가 지연되거나 실패해도 이전 사용자의 목록 캐시를 표시하지 않는다", async ({ page }) => {
  await start(page);
  let newRequests = 0;
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/v1/web/trips", async (route) => {
    if (route.request().headers()["x-user-key"] === "acop_u_other") {
      newRequests += 1;
      if (newRequests === 1) return route.fulfill({ json: { trips: [] } }); // 가져오기 검증
      await gate;
      return route.fulfill({ status: 500, json: { error: { code: "internal_error", message: "새 사용자 조회 실패" } } });
    }
    return route.fulfill({ json: { trips: [{ trip_id: TRIP_ID, title: "A 사용자만의 여행", version: 1, created_at: "2026-10-01T07:00:00+09:00" }] } });
  });
  await page.goto("/trips");
  await expect(page.getByRole("link", { name: /A 사용자만의 여행/ })).toBeVisible();
  await menuLink(page, /마이페이지/);
  const manage = page.getByRole("group", { name: "토큰 관리" });
  await manage.getByLabel("다른 기기의 토큰으로 열기").fill("acop_u_other");
  await manage.getByRole("button", { name: "이 토큰으로 열기" }).click();
  await expect(manage.getByRole("status")).toContainText("이 토큰으로 바꿨어요");
  await menuLink(page, /여행 목록 보기/);
  await expect.poll(() => newRequests).toBeGreaterThan(1);
  try {
    await expect(page.getByText("A 사용자만의 여행", { exact: true })).toHaveCount(0);
  } finally { release(); }
  await expect(page.getByRole("main").getByRole("alert")).toContainText("새 사용자 조회 실패");
  await expect(page.getByText("A 사용자만의 여행", { exact: true })).toHaveCount(0);
});

for (const conflict of [false, true]) {
  test(`날짜 갱신 후 시각만 저장한다: ${conflict ? "409 후에도 편집 초안을 유지" : "성공 후 서버 보정값을 표시"}`, async ({ page, request }) => {
    await start(page);
    await stub(request).scenario({ readingPolls: 0 });
    let view: IntakeView;
    const edits: { revision: number; edits: { field: string; value: unknown }[] }[] = [];
    await page.route("**/v1/web/trip-intakes/**", async (route) => {
      if (route.request().method() === "GET") {
        if (!view) view = await (await route.fetch()).json() as IntakeView;
        return route.fulfill({ json: view });
      }
      if (!route.request().url().endsWith("/edits")) return route.continue();
      const body = route.request().postDataJSON();
      edits.push(body);
      const item = view.sources[0].items[0];
      view.revision += 1;
      if (edits.length === 1) {
        item.fields.date!.value = "2026-10-02";
        item.date = "2026-10-02";
      } else if (conflict && edits.length === 2) {
        item.fields.date!.value = "2026-10-03";
        item.date = "2026-10-03";
        return route.fulfill({ status: 409, json: { error: { code: "stale_revision", message: "그 사이 바뀌었어요", current_revision: view.revision } } });
      } else {
        item.fields.starts_at!.value = "11:05";
      }
      return route.fulfill({ json: view });
    });
    await page.goto("/intakes/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee");
    await expect(page.getByLabel("날짜", { exact: true })).toHaveValue("2026-10-01");
    if (conflict) await page.getByLabel("시작", { exact: true }).fill("11:00");
    await page.getByRole("button", { name: "장소 없음", exact: true }).click();
    await expect(page.getByLabel("날짜", { exact: true })).toHaveValue("2026-10-02");
    if (conflict) await expect(page.getByLabel("시작", { exact: true })).toHaveValue("11:00");
    else await page.getByLabel("시작", { exact: true }).fill("11:00");
    await page.getByRole("button", { name: "날짜·시각 저장" }).click();
    if (conflict) {
      await expect(page.getByLabel("날짜", { exact: true })).toHaveValue("2026-10-03");
      await expect(page.getByLabel("시작", { exact: true })).toHaveValue("11:00");
      await expect(page.getByText("그 사이 바뀌었어요", { exact: true })).toBeVisible();
      await page.getByRole("button", { name: "날짜·시각 저장" }).click();
    }
    await expect(page.getByLabel("시작", { exact: true })).toHaveValue("11:05");
    expect(edits[1]).toEqual({ revision: 2, edits: [{ source_id: "s1", field: "items[0].starts_at", value: "11:00" }] });
    if (conflict) expect(edits[2]).toEqual({ revision: 3, edits: [{ source_id: "s1", field: "items[0].starts_at", value: "11:00" }] });
  });
}
