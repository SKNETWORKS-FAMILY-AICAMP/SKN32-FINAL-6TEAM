import { expect, test, type Page } from "@playwright/test";
import { mockServer, start } from "./helpers";

const ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const path = `/v1/web/trip-intakes/${ID}`;
const card = (page: Page) => page.getByRole("button", { name: /경복궁 관람.*펼쳐서 고치기/ });

test.beforeEach(async ({ page, request }) => {
  await mockServer(request).reset();
  await mockServer(request).scenario({ readingPolls: 0 });
  await start(page);
  await page.goto(`/intakes/${ID}`);
  await card(page).click();
});

test("초안을 취소하면 요청 없이 닫히고, 시간 역전은 저장을 막으며 유효한 날짜·시각만 보낸다", async ({ page, request }) => {
  const server = mockServer(request);
  await page.getByLabel("일정 이름", { exact: true }).fill("취소할 초안");
  await expect(page.getByRole("button", { name: "여행 등록", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "취소", exact: true }).click();
  await expect(page.getByLabel("일정 이름", { exact: true })).toHaveCount(0);
  expect(await server.received("POST", "/edits")).toHaveLength(0);
  await card(page).click();
  await expect(page.getByLabel("일정 이름", { exact: true })).toHaveValue("경복궁 관람");
  await page.getByLabel("끝", { exact: true }).fill("08:00");
  await expect(page.getByText("끝 시각은 시작 시각보다 늦어야 해요.")).toBeVisible();
  await expect(page.getByRole("button", { name: "저장하고 확인" })).toBeDisabled();
  await page.getByLabel("끝", { exact: true }).fill("10:00");
  await page.getByLabel("방문 날짜", { exact: true }).fill("2026-10-02");
  await page.getByRole("button", { name: "저장하고 확인" }).click();
  await expect.poll(async () => (await server.received("POST", "/edits")).length).toBe(1);
  expect((await server.received("POST", "/edits"))[0].body).toEqual({ revision: 1, edits: [
    { source_id: "s1", field: "items[0].date", value: "2026-10-02" },
    { source_id: "s1", field: "items[0].ends_at", value: "10:00" },
  ] });
});

test("지도 검색 실패는 창과 초안을 보존하고, 다시 찾으면 카드 변경을 함께 보낸다", async ({ page, request }) => {
  const server = mockServer(request);
  await page.getByLabel("일정 이름", { exact: true }).fill("궁궐 산책");
  await page.getByRole("button", { name: "업체 이름으로 찾기" }).click();
  const dialog = page.getByRole("dialog", { name: "장소 찾기 지도" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("textbox")).toBeFocused();
  await page.route(`**${path}/edits`, (route) => route.fulfill({ status: 422, json: { error: { code: "place_not_found", message: "찾지 못한 장소입니다" } } }), { times: 1 });
  await dialog.getByRole("textbox").fill("미확인 장소");
  await dialog.getByRole("button", { name: "찾아서 저장" }).click();
  await expect(dialog.getByRole("alert").filter({ hasText: "찾지 못한 장소입니다" })).toBeVisible();
  await expect(dialog.getByRole("textbox")).toHaveValue("미확인 장소");
  await dialog.getByRole("textbox").fill("창덕궁");
  await dialog.getByRole("button", { name: "찾아서 저장" }).click();
  await expect(dialog).toHaveCount(0);
  expect((await server.received("POST", "/edits"))[0].body).toEqual({ revision: 1, edits: [
    { source_id: "s1", field: "items[0].title", value: "궁궐 산책" },
    { source_id: "s1", field: "items[0].place", value: { name: "창덕궁" } },
  ] });
});

test("409 뒤 재조회도 실패해도 초안을 잃지 않고, 최신 판을 읽으면 취소·다시 열기로 이어진다", async ({ page, request }) => {
  await mockServer(request).scenario({ edits: "stale" });
  await page.route(`**${path}`, (route) => route.fulfill({ status: 503, json: { detail: "temporarily unavailable" } }), { times: 1 });
  await page.getByLabel("일정 이름", { exact: true }).fill("보존할 초안");
  await page.getByRole("button", { name: "저장하고 확인" }).click();
  await expect(page.getByText("최신 결과를 불러오지 못했어요.", { exact: false })).toBeVisible();
  await expect(page.getByLabel("일정 이름", { exact: true })).toHaveValue("보존할 초안");
  await expect(page.getByRole("button", { name: "여행 등록", exact: true })).toBeDisabled();
  await page.route(`**${path}`, async (route) => {
    const response = await route.fetch();
    const view = await response.json();
    await route.fulfill({ response, json: { ...view, revision: 2 } });
  });
  await page.getByRole("button", { name: "다시 불러오기", exact: true }).click();
  await expect(page.getByText("다른 화면에서 계획이 바뀌었어요.", { exact: false })).toBeVisible();
  await expect(page.getByLabel("일정 이름", { exact: true })).toHaveValue("보존할 초안");
  await expect(page.getByRole("button", { name: "저장하고 확인" })).toBeDisabled();
  await page.getByRole("button", { name: "취소", exact: true }).click();
  await card(page).click();
  await expect(page.getByLabel("일정 이름", { exact: true })).toBeEnabled();
  await expect(page.getByLabel("일정 이름", { exact: true })).toHaveValue("경복궁 관람");
});

test("장소 없음과 제외는 원래 항목 ID를 사용하고, 삭제 취소는 서버를 부르지 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await page.getByRole("button", { name: "삭제", exact: true }).click();
  await page.getByRole("button", { name: "유지하기" }).click();
  expect(await server.received("POST", "/edits")).toHaveLength(0);
  await page.getByLabel("장소 없음으로 두기").check();
  await page.getByRole("button", { name: "저장하고 확인" }).click();
  await expect(card(page)).toBeVisible();
  expect((await server.received("POST", "/edits"))[0].body?.edits).toEqual([{ source_id: "s1", field: "items[0].place", value: { none: true } }]);
  await card(page).click();
  await page.getByRole("button", { name: "삭제", exact: true }).click();
  await page.getByRole("button", { name: "일정 삭제", exact: true }).click();
  await expect.poll(async () => (await server.received("POST", "/edits")).length).toBe(2);
  expect((await server.received("POST", "/edits"))[1].body?.edits).toEqual([{ source_id: "s1", field: "items[0].removed", value: true }]);
});

test("320·390px에서 카드·시간 입력·지도 창이 화면을 넘지 않고 Esc로 초안을 보존한다", async ({ page }) => {
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 844 });
    await page.getByLabel("일정 이름", { exact: true }).fill("긴 일정 이름 ".repeat(7));
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    for (const label of ["방문 날짜", "시작", "끝"]) {
      const box = await page.getByLabel(label, { exact: true }).boundingBox();
      expect(box!.x).toBeGreaterThanOrEqual(0);
      expect(box!.x + box!.width).toBeLessThanOrEqual(width);
    }
    await page.getByRole("button", { name: "지도 크게 보기" }).click();
    const dialog = page.getByRole("dialog", { name: "장소 찾기 지도" });
    await expect(dialog).toBeVisible();
    expect(await dialog.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(page.getByLabel("일정 이름", { exact: true })).toHaveValue("긴 일정 이름 ".repeat(7));
  }
});

test("날짜 없는 항목은 카드 안내와 여행 첫날 일괄 입력을 함께 제공한다", async ({ page, request }) => {
  await page.route(`**${path}`, async (route) => {
    const response = await route.fetch();
    const view = await response.json();
    view.sources[0].items[0].date = null;
    delete view.sources[0].items[0].fields.date;
    view.check.ready = false;
    view.check.problems = [{ source_id: "s1", field: "items[0].date", code: "no_date", message: "여행 첫날을 알려 주세요" }];
    await route.fulfill({ response, json: view });
  });
  await page.reload();
  await expect(page.getByRole("button", { name: "날짜 확인 필요", exact: true })).toBeVisible();
  await page.getByLabel("여행 첫날", { exact: true }).fill("2026-10-12");
  await page.getByRole("button", { name: "저장", exact: true }).click();
  const server = mockServer(request);
  await expect.poll(async () => (await server.received("POST", "/edits")).length).toBe(1);
  expect((await server.received("POST", "/edits"))[0].body?.edits).toEqual([{ field: "trip.first_day", value: "2026-10-12" }]);
});
