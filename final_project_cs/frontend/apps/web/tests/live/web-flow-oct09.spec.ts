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
  await form.getByLabel("장소 검색", { exact: true }).fill("올리브영");
  await form.getByRole("list", { name: "장소 검색 결과" }).getByRole("button", { name: /올리브영 명동 플래그십/ }).click();
  await form.getByLabel("일정 종류").selectOption("dining");
  await form.getByRole("button", { name: "일정에 추가", exact: true }).click();
  await expect.poll(async () => (await mock.received("POST", "/edits")).length).toBe(1);
  const edits = (await mock.received("POST", "/edits"))[0].body!.edits as { field: string; value: unknown }[];
  expect(edits).toHaveLength(6);
  expect(edits.find((entry) => entry.field.endsWith(".kind"))?.value).toBe("dining");
  await expect(page.getByRole("article", { name: "올리브영 명동 플래그십" }).filter({ hasText: "저녁 식사" })).toBeVisible();
  await expect(form).not.toBeVisible();
});

test("검증 단계 점선 이동 줄에 출발과 도착 시각 및 머무름이 나온다", async ({ page, request }) => {
  await mockServer(request).scenario({ review: "on", board: "rich", readingPolls: 0 });
  await start(page);
  await page.goto(`/intakes/${INTAKE}`);
  const moves = page.locator('li[data-type="move"]');
  await expect(moves.first()).toContainText("출발");
  await expect(moves.first()).toContainText(/도착\s+\d{2}:\d{2}/);
  await expect(moves.first()).toContainText("머무름");
});
