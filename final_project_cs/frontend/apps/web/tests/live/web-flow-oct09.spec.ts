import { expect, test } from "@playwright/test";
import { mockServer, start, checkPlan } from "./helpers";

const INTAKE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

test("설문 자유입력은 원문으로 저장하고 취소 후 다시 입력할 수 있으며 화살표가 입력 중 질문을 넘기지 않는다", async ({ page, request }) => {
  const mock = mockServer(request);
  await mock.scenario({ questions: "two", readingPolls: 999 });
  await start(page);
  await page.goto("/trips/new");
  await page.getByLabel("나의 여행 계획").fill("10/1 09:00 경복궁 관람");
  await checkPlan(page);
  const pager = page.getByRole("region", { name: "질문 2개" });
  await expect(pager.getByRole("button", { name: "이 질문 건너뛰기" })).toHaveCount(0);
  await pager.getByLabel("직접 입력").fill("택시 + 버스");
  await page.keyboard.press("ArrowRight");
  await expect(pager).toContainText("1 / 2");
  await pager.getByRole("button", { name: "답변 저장" }).click();
  await expect.poll(async () => (await mock.received("POST", "/survey"))[0]?.body).toEqual({ answers: { preferred_mobility: { custom: "택시 + 버스" } } });
  await expect(pager).toContainText("2 / 2");
  await pager.getByRole("button", { name: "이전 질문 보기" }).click();
  await expect(pager.getByLabel("직접 입력")).toHaveValue("택시 + 버스");
  await pager.getByRole("button", { name: "답변 취소하고 다시 입력" }).click();
  await expect.poll(async () => (await mock.received("POST", "/survey"))[1]?.body).toEqual({ answers: { preferred_mobility: null } });
  await expect(pager.getByLabel("직접 입력")).toHaveValue("");
  await pager.getByLabel("직접 입력").fill("지하철 + 택시");
  await pager.getByRole("button", { name: "답변 저장" }).click();
  await expect.poll(async () => (await mock.received("POST", "/survey"))[2]?.body).toEqual({ answers: { preferred_mobility: { custom: "지하철 + 택시" } } });
});

test("검증 목록에서 일정을 추가하면 6개 필드를 한 판으로 보내고 새 카드에 반영한다", async ({ page, request }) => {
  const mock = mockServer(request);
  await mock.scenario({ review: "on", board: "rich", readingPolls: 0 });
  await start(page);
  await page.goto(`/intakes/${INTAKE}`);
  await page.locator('[data-insert-near] > button').click();
  const form = page.getByRole("form", { name: "일정 추가" });
  await form.getByLabel("일정 이름").fill("저녁 식사");
  await form.getByLabel("날짜", { exact: true }).fill("2026-10-01");
  await form.getByLabel("시작", { exact: true }).fill("18:30");
  await form.getByLabel("끝", { exact: true }).fill("19:30");
  await page.getByRole("searchbox", { name: "장소 검색", exact: true }).fill("올리브영");
  await page.getByRole("list", { name: "장소 검색 결과" }).getByRole("button", { name: /올리브영 명동 플래그십/ }).click();
  await form.getByLabel("일정 종류").selectOption("dining");
  await form.getByRole("button", { name: "일정에 추가", exact: true }).click();
  await expect.poll(async () => (await mock.received("POST", "/edits")).length).toBe(1);
  const edits = (await mock.received("POST", "/edits"))[0].body!.edits as { field: string; value: unknown }[];
  expect(edits).toHaveLength(6);
  expect(edits.find((entry) => entry.field.endsWith(".kind"))?.value).toBe("dining");
  await expect(page.getByRole("article", { name: "올리브영 명동 플래그십" }).filter({ hasText: "저녁 식사" })).toBeVisible();
  await expect(form).not.toBeVisible();
});

test("검증 이동은 출발만 표시하다 펼치면 도착을 표시하고 수단·소요·여유를 유지한다", async ({ page, request }) => {
  await mockServer(request).scenario({ review: "on", board: "rich", readingPolls: 0 });
  await start(page);
  await page.goto(`/intakes/${INTAKE}`);
  const moves = page.locator('li[data-type="move"]');
  const first = moves.first();
  await expect(first.locator("[data-move-departure]")).toHaveText("10:30");
  await expect(first.locator("[data-move-arrival]")).toHaveAttribute("aria-hidden", "true");
  await expect(first.locator("[data-move-arrival]")).toHaveCSS("opacity", "0");
  await expect(first).toContainText("지하철 3호선 9분 · 0.6km");
  await expect(first).toContainText("여유 21분");
  await first.getByRole("button", { expanded: false }).filter({ hasText: "지하철 3호선" }).click();
  await expect(first.locator("[data-move-arrival]")).toHaveAttribute("aria-hidden", "false");
  await expect(first.locator("[data-move-arrival]")).toHaveCSS("opacity", "1");
  await expect(first.locator("[data-move-arrival]")).toHaveText("~10:39");
});
