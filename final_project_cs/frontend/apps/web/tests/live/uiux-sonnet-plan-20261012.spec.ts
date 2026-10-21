import { expect, test, type Page } from "@playwright/test";
import { mockServer } from "./helpers";
import { changedBadge, head, openFinished, typeTimes, type Json } from "./plan-check-kit";

// mock 서버 시험: 필터·키보드·동시 변경 요청의 화면 반응을 확인합니다.
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const title = (page: Page) => page.getByRole("button", { name: /^계획 이름 · / });
const timeNotice = (page: Page) => page.getByRole("status").filter({ hasText: /개 일정의 시간을 바꿨어요/ });
async function changeTime(page: Page) {
  await page.getByRole("button", { name: /^광장시장 시간 고치기/ }).click();
  const form = await typeTimes(page.getByRole("form", { name: "광장시장 시간 고치기" }));
  await form.getByLabel("시작", { exact: true }).fill("11:30");
  await form.getByRole("button", { name: "적용", exact: true }).click();
  await expect(timeNotice(page)).toBeVisible();
  await expect(changedBadge(page)).toBeVisible();
}

for (const key of ["Enter", "Escape"]) {
  test(`계획 이름 편집을 ${key}로 끝내면 제목 버튼에 초점이 돌아온다`, async ({ page, request }) => {
    const api = await openFinished(page, request, undefined, { intakeEvents: "off" });
    await title(page).click();
    await title(page).click();
    const field = page.getByRole("textbox", { name: "계획 이름", exact: true });
    await expect(field).toBeFocused();
    await field.fill("초점 복원 확인 여행");
    await field.press(key);
    await expect(field).toHaveCount(0);
    await expect(title(page)).toBeFocused();
    const edits = await api.received("POST", "/edits");
    expect(edits).toHaveLength(key === "Enter" ? 1 : 0);
    if (key === "Enter") expect(JSON.stringify(edits[0].body)).toContain("초점 복원 확인 여행");
  });
}

for (const key of ["Enter", "Space"]) {
  test(`목록 머리를 끈 직후 손잡이 첫 ${key} 입력이 동작한다`, async ({ page, request }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await openFinished(page, request, undefined, { intakeEvents: "off" });
    await expect(page.getByRole("status").filter({ hasText: "계획 확인 화면이에요" })).toHaveCount(0);
    // 떠 있는 머리의 바깥 빈칸은 본문으로 통과합니다. 실제 머리 자식인 날짜 칩 사이를 끕니다.
    const header = page.locator("header[class*=sheetHead]");
    const start = await header.evaluate(root => {
      const tabs = [...root.querySelectorAll<HTMLElement>('[role="tab"]')];
      const first = tabs[0].getBoundingClientRect(), second = tabs[1].getBoundingClientRect();
      const x = (first.right + second.left) / 2, y = first.y + first.height / 2;
      const target = document.elementFromPoint(x, y);
      return { x, y, gap: second.left - first.right, hitsHeadBackground: Boolean(target && root.contains(target) && !target.closest("button,a,input,select,textarea")) };
    });
    expect(start.gap).toBeGreaterThan(0);
    expect(start.hitsHeadBackground).toBe(true);
    const { x, y } = start;
    await page.mouse.move(x, y); await page.mouse.down();
    await page.mouse.move(x, y - 75, { steps: 8 }); await page.mouse.up();
    await expect(page.locator("[data-sheet]")).toHaveAttribute("data-sheet", "custom");
    await page.getByRole("button", { name: "목록 높이 바꾸기" }).focus();
    await page.keyboard.press(key);
    await expect(page.locator("[data-sheet]")).toHaveAttribute("data-sheet", "half");
  });
}

test("변경을 모두 되돌린 뒤 새로 바꾸면 이전 필터와 변경 메뉴가 되살아나지 않는다", async ({ page, request }) => {
  await openFinished(page, request, undefined, { intakeEvents: "off" });
  await changeTime(page);
  await changedBadge(page).click();
  await expect(page.getByRole("region", { name: "변경 관리" })).toBeVisible();
  await timeNotice(page).getByRole("button", { name: "되돌리기", exact: true }).click();
  await expect(changedBadge(page)).toHaveCount(0);
  await changeTime(page);
  await expect(changedBadge(page)).toHaveAttribute("aria-expanded", "false");
  await expect(page.getByRole("region", { name: "변경 관리" })).toHaveCount(0);
  await expect(page.getByText("바뀐 곳만 보는 중이에요", { exact: true })).toHaveCount(0);
});

test("잠금 요청이 진행 중이면 이전 시간 변경 토스트의 되돌리기가 추가 요청을 보내지 않는다", async ({ page, request }) => {
  await openFinished(page, request, undefined, { intakeEvents: "off" });
  await changeTime(page);
  await head(page, "경복궁 관람").click();
  let release!: () => void;
  const held = new Promise<void>((resolve) => { release = resolve; });
  let hits = 0;
  await page.route("**/v1/web/trip-intakes/**/edits", async (route) => {
    hits += 1;
    await held;
    await route.continue();
  });
  try {
    await page.getByRole("button", { name: "경복궁 관람 꼭 넣을 일정으로 고정", exact: true }).click();
    await expect.poll(() => hits).toBe(1);
    await timeNotice(page).getByRole("button", { name: "되돌리기", exact: true }).click();
    await expect(page.getByRole("alert").filter({ hasText: "바뀐 일정을 다시 확인하는 중이에요" })).toBeVisible();
    expect(hits).toBe(1);
    await expect(page.getByRole("button", { name: "경복궁 관람 꼭 넣을 일정으로 고정", exact: true })).toHaveAttribute("aria-disabled", "true");
  } finally { release(); }
  await expect(page.getByRole("button", { name: "경복궁 관람 고정 풀기", exact: true })).toBeVisible();
});

test("확인 실패 안내가 해소된 뒤 같은 실패가 다시 생기면 안내를 다시 표시한다", async ({ page, request }) => {
  let failed = true;
  const withFailure = (view: Json) => { view.review_error = failed ? "review unavailable" : null; };
  await page.route("**/v1/web/trip-intakes/**/edits", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    withFailure(body);
    await route.fulfill({ response, json: body });
  });
  await openFinished(page, request, withFailure, { intakeEvents: "off" });
  const notice = page.getByRole("alert").filter({ hasText: "장소·운영시간·이동 확인 결과를 만들지 못했어요" });
  await expect(notice).toBeVisible();
  await notice.getByRole("button", { name: "닫기", exact: true }).click();
  for (const [failure, name] of [[false, "확인 복구 여행"], [true, "다시 확인 실패 여행"]] as const) {
    failed = failure;
    await title(page).click(); await title(page).click();
    const field = page.getByRole("textbox", { name: "계획 이름", exact: true });
    await field.fill(name); await field.press("Enter");
    await expect(title(page)).toHaveAccessibleName(`계획 이름 · ${name}`);
    if (!failure) await expect(notice).toHaveCount(0);
  }
  await expect(notice).toBeVisible();
});
