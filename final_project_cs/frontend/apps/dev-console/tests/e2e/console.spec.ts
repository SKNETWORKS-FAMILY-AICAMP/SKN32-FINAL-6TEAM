import { expect, test, type Page } from "@playwright/test";

const main = (page: Page) => page.locator("#main-content");
const result = (page: Page) => main(page).getByRole("region", { name: "기대 결과 대조" });
const stepDetail = (page: Page) => main(page).getByRole("region", { name: "선택한 단계 상세" });

async function startRun(page: Page) {
  const previous = new URL(page.url()).searchParams.get("run");
  await main(page).getByRole("button", { name: "샘플 테스트 실행", exact: true }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("run")).not.toBe(previous);
  const id = new URL(page.url()).searchParams.get("run");
  expect(id).toBeTruthy();
  return id!;
}

async function waitForCompletion(page: Page) {
  await expect(main(page).getByText("실행 완료", { exact: true })).toBeVisible();
}

async function expectNoHorizontalOverflow(page: Page) {
  const size = await page.evaluate(() => ({ width: window.innerWidth, content: document.documentElement.scrollWidth }));
  expect(size.content).toBeLessThanOrEqual(size.width);
}

test("첫 실행은 수동으로 시작하고 조회·판정·출력을 확인하며 변경된 입력과 새 실행을 구분한다", async ({ page }) => {
  await page.goto("/teams");
  await expect(main(page).getByRole("heading", { name: "입력을 확인하고 첫 테스트를 실행하세요" })).toBeVisible();
  expect(new URL(page.url()).searchParams.has("run")).toBe(false);
  await expect(main(page).getByRole("link", { name: "실행 상세 링크" })).toHaveCount(0);

  const firstId = await startRun(page);
  await expect(main(page).getByRole("button", { name: "샘플 실행 중…" })).toBeDisabled();
  await waitForCompletion(page);
  await expect(result(page).getByRole("heading", { name: "마감 조건 초과" })).toBeVisible();

  await main(page).getByRole("button", { name: /조회 응답/ }).click();
  await stepDetail(page).getByRole("button", { name: "조회값", exact: true }).click();
  await expect(stepDetail(page).getByRole("row", { name: /입장 마감 16:30/ })).toBeVisible();
  await main(page).getByRole("button", { name: /3구간.*비교·판정/ }).click();
  await stepDetail(page).getByRole("button", { name: "비교·판정", exact: true }).click();
  await expect(stepDetail(page).getByRole("row", { name: /예상 도착.*16:45.*16:30.*15분 초과/ })).toBeVisible();
  await stepDetail(page).getByRole("button", { name: "출력", exact: true }).click();
  await expect(stepDetail(page).locator("pre")).toContainText('"deadline_status": "conflict"');

  await main(page).getByLabel("예상 도착 시각", { exact: true }).fill("16:00");
  await expect(main(page).getByText(/입력이 변경되었습니다. 아래 결과는 이전 실행의 입력 기준입니다/)).toBeVisible();
  await expect(result(page).getByRole("heading", { name: "마감 조건 초과" })).toBeVisible();
  const secondId = await startRun(page);
  expect(secondId).not.toBe(firstId);
  await waitForCompletion(page);
  await expect(result(page).getByRole("heading", { name: "마감 조건 충족" })).toBeVisible();
  await expect(main(page).getByText(/입력이 변경되었습니다/)).toHaveCount(0);

  await page.reload();
  await waitForCompletion(page);
  expect(new URL(page.url()).searchParams.get("run")).toBe(secondId);
  await expect(main(page).getByLabel("예상 도착 시각", { exact: true })).toHaveValue("16:00");
  await expect(result(page).getByRole("heading", { name: "마감 조건 충족" })).toBeVisible();
});

test("요식업은 휴게시간과 예약을 표시하고 이동은 선택한 교통수단의 도착 시각을 반환한다", async ({ page }) => {
  await page.goto("/teams");
  await main(page).getByRole("group", { name: "에이전트팀 선택" }).getByRole("button", { name: "요식업", exact: true }).click();
  await expect(main(page).getByLabel("예약 시각", { exact: true })).toHaveValue("14:30");
  await startRun(page);
  await waitForCompletion(page);
  await expect(result(page).getByRole("heading", { name: "휴게시간 이용 확인 필요" })).toBeVisible();
  await main(page).getByRole("button", { name: /조회 응답/ }).click();
  await stepDetail(page).getByRole("button", { name: "조회값", exact: true }).click();
  await expect(stepDetail(page).getByRole("row", { name: /휴게시간 15:00–17:00/ })).toBeVisible();
  await main(page).getByRole("button", { name: /3구간.*비교·판정/ }).click();
  await stepDetail(page).getByRole("button", { name: "비교·판정", exact: true }).click();
  await expect(stepDetail(page).getByRole("row", { name: /예약 보존 14:30 예약 유지/ })).toBeVisible();

  await main(page).getByRole("group", { name: "에이전트팀 선택" }).getByRole("button", { name: "이동", exact: true }).click();
  await main(page).getByLabel("출발 시각", { exact: true }).fill("15:40");
  await main(page).getByLabel("선호 이동수단", { exact: true }).selectOption("taxi");
  await startRun(page);
  await waitForCompletion(page);
  await expect(result(page).getByRole("heading", { name: "택시 · 16:03 도착" })).toBeVisible();
  await expect(stepDetail(page).getByRole("row", { name: /택시 16:03 도착.*선호 조건 일치.*선택/ })).toBeVisible();
  await stepDetail(page).getByRole("button", { name: "출력", exact: true }).click();
  await expect(stepDetail(page).locator("pre")).toContainText('"duration_minutes": 23');
});

test("도구 실패에는 판정 결과가 없고 재실행은 새 ID를 만들며 정상 조건으로 회복한다", async ({ page }) => {
  await page.goto("/teams");
  await main(page).getByLabel("샘플 응답 조건", { exact: true }).selectOption("tool-error");
  const failedId = await startRun(page);
  await expect(main(page).getByText("실행 실패", { exact: true })).toBeVisible();
  await expect(main(page).getByRole("alert").first()).toContainText("샘플 도구 응답 실패");
  await expect(result(page)).toHaveCount(0);

  await main(page).getByRole("button", { name: "같은 입력으로 재실행", exact: true }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("run")).not.toBe(failedId);
  const retriedId = new URL(page.url()).searchParams.get("run");
  expect(retriedId).toBeTruthy();
  await expect(main(page).getByRole("link", { name: failedId, exact: true })).toHaveAttribute("href", `/runs/${failedId}`);
  await expect(result(page)).toHaveCount(0);
  await expect(main(page).getByText("실행 실패", { exact: true })).toBeVisible();
  await expect(result(page)).toHaveCount(0);

  await main(page).getByLabel("샘플 응답 조건", { exact: true }).selectOption("normal");
  const recoveredId = await startRun(page);
  expect(recoveredId).not.toBe(retriedId);
  await waitForCompletion(page);
  await expect(result(page)).toBeVisible();
  await expect(main(page).getByRole("alert")).toHaveCount(0);
});

test("저장 사례로 A/B를 실행하면 입력이 고정되고 새로고침과 상세 링크에서도 같은 기록을 확인한다", async ({ page }) => {
  await page.goto("/teams");
  await main(page).getByLabel("예상 도착 시각", { exact: true }).fill("16:40");
  await main(page).getByLabel("관람 시간 (분)", { exact: true }).fill("45");
  await startRun(page);
  await waitForCompletion(page);
  await main(page).getByText("테스트 사례로 저장", { exact: true }).click();
  await main(page).getByLabel("사례 이름", { exact: true }).fill("입장 마감 회귀 사례");
  await main(page).getByRole("button", { name: "사례 저장", exact: true }).click();
  await main(page).getByRole("link", { name: "이 입력으로 A/B 비교하기" }).click();
  await expect(page).toHaveURL(/\/cases\?case=/);
  await expect(main(page).getByRole("button", { name: /입장 마감 회귀 사례/ })).toHaveAttribute("aria-pressed", "true");
  expect(new URL(page.url()).searchParams.has("comparison")).toBe(false);
  await main(page).getByRole("button", { name: "A/B 비교 실행", exact: true }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("comparison")).toBeTruthy();
  const comparisonId = new URL(page.url()).searchParams.get("comparison");
  const a = main(page).getByRole("region", { name: "샘플 버전 A 결과", exact: true });
  const b = main(page).getByRole("region", { name: "샘플 버전 B 결과", exact: true });
  await expect(a.getByText("실행 완료", { exact: true })).toBeVisible();
  await expect(b.getByText("실행 완료", { exact: true })).toBeVisible();
  await expect(a.getByText("기대와 불일치", { exact: true })).toBeVisible();
  await expect(b.getByText("기대와 일치", { exact: true })).toBeVisible();

  await a.getByText("이 실행의 요청 JSON", { exact: true }).click();
  await b.getByText("이 실행의 요청 JSON", { exact: true }).click();
  const requestA = JSON.parse(await a.locator("pre").innerText());
  const requestB = JSON.parse(await b.locator("pre").innerText());
  expect(requestA.version).toBe("A");
  expect(requestB.version).toBe("B");
  expect({ ...requestA, version: undefined }).toEqual({ ...requestB, version: undefined });
  expect(requestA.input).toMatchObject({ time: "16:40", durationMinutes: 45 });
  const detailHref = await a.getByRole("link", { name: "버전 A 실행 상세 →" }).getAttribute("href");
  expect(detailHref).toMatch(/^\/runs\//);

  await main(page).getByRole("button", { name: /식사와 휴게시간 겹침/ }).click();
  const comparisonPanel = main(page).locator("section").filter({ has: page.getByRole("heading", { name: "A/B 비교 결과", exact: true }) });
  await expect(comparisonPanel.getByText("입장 마감 회귀 사례", { exact: true })).toBeVisible();
  await page.reload();
  expect(new URL(page.url()).searchParams.get("comparison")).toBe(comparisonId);
  await expect(a.getByText("기대와 불일치", { exact: true })).toBeVisible();
  await expect(b.getByText("기대와 일치", { exact: true })).toBeVisible();
  await a.getByText("이 실행의 요청 JSON", { exact: true }).click();
  expect(JSON.parse(await a.locator("pre").innerText())).toEqual(requestA);
  await a.getByRole("link", { name: "버전 A 실행 상세 →" }).click();
  await expect(page).toHaveURL(new RegExp(`${detailHref}$`));
  await expect(main(page).getByRole("heading", { name: "실행 상세", exact: true })).toBeVisible();
  await expect(result(page).getByText("기대 결과 불일치", { exact: true })).toBeVisible();
});

test("코어 통합은 두 팀을 같은 구간에 배치하고 이동 결과를 액티비티에 연결한다", async ({ page }) => {
  await page.goto("/integration");
  await expect(main(page).getByRole("heading", { name: "코어 통합 테스트", exact: true })).toBeVisible();
  const id = await startRun(page);
  await waitForCompletion(page);
  const dining = main(page).getByRole("button", { name: /예약·휴게시간 확인/ });
  const mobility = main(page).getByRole("button", { name: /경로·도착 시각 조회/ });
  await expect(dining).toContainText("2구간 · 완료");
  await expect(mobility).toContainText("2구간 · 완료");
  await main(page).getByRole("button", { name: /입장·관람 조건 판정/ }).click();
  await stepDetail(page).getByRole("button", { name: "입력", exact: true }).click();
  const activityInput = JSON.parse(await stepDetail(page).locator("pre").innerText());
  expect(activityInput.arrival_source_step).toBe(`${id}:mobility`);
  expect(activityInput.arrival).toBe("16:45");
  await main(page).getByRole("button", { name: /계약 검증·결과 취합/ }).click();
  await stepDetail(page).getByRole("button", { name: "비교·판정", exact: true }).click();
  await expect(stepDetail(page).getByRole("row", { name: /결과 연결 같은 실행 ID의 세 팀 출력 취합/ })).toBeVisible();
  await stepDetail(page).getByRole("button", { name: "출력", exact: true }).click();
  const coreOutput = JSON.parse(await stepDetail(page).locator("pre").innerText());
  expect(Object.keys(coreOutput).sort()).toEqual(["activity", "dining", "mobility"]);
  expect(coreOutput.mobility.arrival).toBe(coreOutput.activity.arrival);
  await expect(result(page).getByText("기대 결과 일치", { exact: true })).toBeVisible();
});

test("없는 실행·사례·비교는 오류와 복구 경로를 표시하며 자동 실행하지 않는다", async ({ page }) => {
  await page.goto("/runs/missing-run");
  await expect(main(page).getByRole("alert")).toContainText("실행 기록을 찾을 수 없습니다");
  await expect(result(page)).toHaveCount(0);
  await expect(main(page).getByRole("button", { name: "다시 불러오기", exact: true })).toBeVisible();

  await page.goto("/teams?case=missing-case");
  await expect(main(page).getByRole("alert")).toContainText("테스트 사례를 찾을 수 없습니다");
  await expect(main(page).getByRole("button", { name: "샘플 테스트 실행", exact: true })).toBeDisabled();
  expect(new URL(page.url()).searchParams.has("run")).toBe(false);
  await main(page).getByRole("link", { name: "새 테스트 입력 열기", exact: true }).click();
  await expect(main(page).getByRole("button", { name: "샘플 테스트 실행", exact: true })).toBeEnabled();

  await page.goto("/cases?comparison=missing-comparison");
  await expect(main(page).getByRole("alert")).toContainText("비교 기록을 찾을 수 없습니다");
  await expect(main(page).getByRole("link", { name: "사례 목록으로 돌아가기", exact: true })).toBeVisible();
});

test("320px 화면에서 메뉴·비교 결과·연결 안내를 가로 넘침 없이 사용한다", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto("/teams");
  await expect(main(page).getByRole("heading", { name: "에이전트 테스트", exact: true })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  const navigation = page.getByRole("navigation", { name: "개발팀 메뉴" });
  await navigation.getByRole("link", { name: "코어 통합 테스트", exact: true }).click();
  await expect(main(page).getByRole("heading", { name: "코어 통합 테스트", exact: true })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await navigation.getByRole("link", { name: "사례·버전 비교", exact: true }).click();
  await main(page).getByRole("button", { name: "A/B 비교 실행", exact: true }).click();
  await expect(main(page).getByRole("region", { name: "샘플 버전 B 결과", exact: true }).getByText("기대와 일치", { exact: true })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await navigation.getByRole("link", { name: "연결 안내", exact: true }).click();
  await expect(main(page).getByRole("heading", { name: "개발팀과 연결하는 방법", exact: true })).toBeVisible();
  await main(page).getByRole("button", { name: "공용 개발 서버", exact: true }).click();
  await expect(main(page).getByText("공용 코어가 서버에 연결된 팀 버전을 호출합니다.", { exact: true })).toBeVisible();
  await expect(main(page).getByText("실제 API 미연결", { exact: true })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  expect(errors).toEqual([]);
});
