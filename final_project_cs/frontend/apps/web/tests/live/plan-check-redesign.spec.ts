import { expect, test, type Page } from "@playwright/test";
import { mockServer, start } from "./helpers";
import { card, changedBadge, head, INTAKE, needsBadge, openFinished, pin, sheet, toast } from "./plan-check-kit";

/**
 * `[2026-10-04 사용자 지시]` 계획 확인 화면을 고친 것들(요구 목록: `wiki/records/plans/2026-10-04_2230_계획확인_화면_개선_요구목록.md`)을 지키는 화면 시험.
 * mock 서버 시험이다 — 화면이 무엇을 보내고 어떻게 반응하는지를 본다. 서버가 실제로 무엇을 답하는지는 실서버 확인이 따로 본다.
 */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const bodyOf = (page: Page) => page.locator("div[class*=sheetBody]");

// ── 읽는 화면: 단계 점 ─────────────────────────────────────────────────────────

test("읽는 화면의 단계 점: 선이 닿은 점만 체크되고(받았어요 → 일정 읽기 …), 선은 동그라미 뒤에 그려진다", async ({ page, request }) => {
  await mockServer(request).scenario({ readingPolls: 99, intakeEvents: "off" });
  await start(page);
  await page.goto(`/intakes/${INTAKE}`);
  const steps = page.locator("ol[class*=steps] li");
  await expect(steps).toHaveCount(4);
  await expect(steps.first()).toHaveAttribute("data-state", "done");                              // 받았어요: 서버가 받았으니 채워져 있다
  await expect(steps.nth(1)).toHaveAttribute("data-state", "current");                            // 일정 읽기: 아직 선이 거기까지 안 찼다
  await expect(steps.nth(2)).toHaveAttribute("data-state", "waiting");
  const layers = await page.evaluate(() => {
    const track = document.querySelector("div[class*=track]")!, list = document.querySelector("ol[class*=steps]")!;
    return { track: getComputedStyle(track).zIndex, steps: getComputedStyle(list).zIndex, position: getComputedStyle(list).position };
  });
  expect(layers.position).toBe("relative");
  expect(Number(layers.steps)).toBeGreaterThan(Number(layers.track));                              // 점이 선 위에 있어서 동그라미 안에 선이 비치지 않는다
});

// ── 상단바 · 계획 이름 ─────────────────────────────────────────────────────────

test("결과 화면의 상단바는 투명하고 지도가 맨 위까지 이어지며, 홈 표시·계획 이름·메뉴만 지도 위에 떠 있다", async ({ page, request }) => {
  await openFinished(page, request);
  const header = page.locator("header[class*=header]").first();
  await expect(header).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
  const frame = (await page.locator('div[class$="__device"]').boundingBox())!;
  const map = (await page.getByRole("region", { name: "여행 지도" }).boundingBox())!;
  expect(Math.abs(map.y - frame.y)).toBeLessThan(2);                                                // 지도가 상단바 아래가 아니라 맨 위에서 시작한다
  await expect(page.getByRole("link", { name: /triPilot — 소개 화면/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /^계획 이름 · / })).toBeVisible();
  await expect(page.getByRole("button", { name: "메뉴", exact: true })).toBeVisible();
});

test("계획 이름은 눌러야 연필이 나온다: 이름 → 연필 → 입력칸 → Enter 로 저장", async ({ page, request }) => {
  const server = await openFinished(page, request);
  const pencil = page.getByRole("button", { name: /^계획 이름 바꾸기 · 지금 이름은 / });
  await expect(pencil).toHaveCount(0);                                                              // 평소에는 연필이 없다
  await page.getByRole("button", { name: /^계획 이름 · / }).click();
  await expect(pencil).toBeVisible();
  await pencil.click();
  const field = page.getByRole("textbox", { name: "계획 이름" });
  await field.fill("가을 서울 여행");
  await field.press("Enter");
  await expect.poll(async () => JSON.stringify((await server.received("POST", "/edits")).at(-1)?.body ?? {})).toContain("가을 서울 여행");
});

// ── 시트 머리 · 접기 ───────────────────────────────────────────────────────────

test("시트 머리: 문장 대신 「! 2」 표시 하나 — 눌러서 확인 필요만 모아 보고 다시 눌러 전체로 돌아온다", async ({ page, request }) => {
  await openFinished(page, request);
  await expect(page.locator("p[class*=count]")).not.toContainText("장소");                           // 머리에 문장은 없다(스크린 리더용 알림 문장은 따로 있다)
  await expect(needsBadge(page)).toHaveText("!2");
  await needsBadge(page).click();
  await expect(page.getByText("확인이 필요한 곳만 보는 중이에요")).toBeVisible();
  await expect(card(page, "경복궁 관람")).toHaveCount(0);
  await expect(card(page, "올리브영")).toBeVisible();
  await needsBadge(page).click();
  await expect(card(page, "경복궁 관람")).toBeVisible();
});

test("시트를 끝까지 내리면 머리·날짜 칩·목록을 모두 접고 손잡이와 「전체 자동 추천」 줄만 남는다", async ({ page, request }) => {
  await openFinished(page, request);
  const handle = page.getByRole("button", { name: "목록 높이 바꾸기" });
  await handle.click();
  await handle.click();
  await expect(page.locator("[data-sheet]")).toHaveAttribute("data-sheet", "peek");
  await expect(page.locator("[data-compact]")).toHaveCount(1);
  await expect(page.getByRole("heading", { name: "계획 확인" })).toBeHidden();
  await expect(needsBadge(page)).toBeHidden();
  await expect(bodyOf(page)).toBeHidden();
  await expect(page.getByRole("button", { name: /^전체 자동 추천/ })).toBeVisible();
  await expect(handle).toBeVisible();
  await handle.click();                                                                              // 다시 눌러 중간으로 돌아오면 목록이 돌아온다
  await expect(card(page, "경복궁 관람")).toBeVisible();
});

// ── 카드 · 이동 줄 ─────────────────────────────────────────────────────────────

test("이동 줄은 시간과 거리만 말한다(수단은 아이콘) — 같은 말이 두 번 나오지 않고, 통과한 구간에는 체크가 붙지 않는다", async ({ page, request }) => {
  await openFinished(page, request);
  const second = page.getByRole("button", { name: /지하철 1호선.*16분 · 1\.5km/ });
  await expect(second.locator("span[class*=moveText]")).toHaveText("16분 · 1.5km");                   // 눈에 보이는 말은 이것뿐(수단 이름은 화면 읽기용으로만 있다)
  await expect(second.getByRole("img")).toHaveCount(0);                                              // 통과(✓)는 표시하지 않는다
  const first = page.getByRole("button", { name: /지하철 3호선.*9분 · 0\.6km/ });
  await expect(first.getByRole("img", { name: "확인 필요" })).toBeVisible();                           // 봐야 하는 구간만 표시한다
});

test("카드 옆 표시는 「확인 필요」와 「변경 완료」뿐이다 — 「조정」은 없다", async ({ page, request }) => {
  await openFinished(page, request);
  await expect(page.getByText("조정", { exact: true })).toHaveCount(0);
  await expect(page.getByText("확인 필요", { exact: true })).toHaveCount(1);                           // 올리브영 하나
  await expect(card(page, "광장시장")).not.toContainText("유지");
  await head(page, "올리브영").click();
  await card(page, "올리브영").getByRole("button", { name: "자동 추천" }).click();
  await expect(toast(page, "대체 후보 1순위로 바꿨어요")).toBeVisible();
  await expect(card(page, "올리브영 광화문점")).toContainText("변경 완료");
  await expect(card(page, "올리브영 광화문점")).toContainText("바뀜 · 이전 올리브영 인사동점");
});

test("카드를 다시 누르면 강조가 풀리고, 지도의 핀도 다시 누르면 풀린다", async ({ page, request }) => {
  await openFinished(page, request);
  await head(page, "경복궁 관람").click();
  await expect(head(page, "경복궁 관람")).toHaveAttribute("aria-expanded", "true");
  await expect(pin(page, "1. 경복궁 관람")).toHaveAttribute("aria-pressed", "true");
  await head(page, "경복궁 관람").click();                                                            // 한 번 더: 접히고 강조가 풀린다
  await expect(head(page, "경복궁 관람")).toHaveAttribute("aria-expanded", "false");
  await expect(pin(page, "1. 경복궁 관람")).toHaveAttribute("aria-pressed", "false");
  await pin(page, "3. 광장시장").dispatchEvent("click");                                              // 핀으로 고르고
  await expect(pin(page, "3. 광장시장")).toHaveAttribute("aria-pressed", "true");
  await expect(head(page, "광장시장")).toHaveAttribute("aria-expanded", "true");
  await pin(page, "3. 광장시장").dispatchEvent("click");                                              // 핀을 다시 누르면 풀린다
  await expect(pin(page, "3. 광장시장")).toHaveAttribute("aria-pressed", "false");
  await expect(head(page, "광장시장")).toHaveAttribute("aria-expanded", "false");
});

// ── 시간 고치기 ────────────────────────────────────────────────────────────────

test("카드 왼쪽의 시간을 누르면 그 자리에 시간 편집기가 열린다: 끝이 시작보다 빠르면 보내기 전에 막고, 고친 값만 서버로 간다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await page.getByRole("button", { name: /^경복궁 관람 시간 고치기/ }).click();
  const form = page.getByRole("form", { name: "경복궁 관람 시간 고치기" });
  await form.getByLabel("끝", { exact: true }).fill("08:00");                                                         // 시작(09:00)보다 빠르다
  await expect(form.getByRole("alert")).toHaveText("끝 시각이 시작보다 빨라요.");
  await expect(form.getByRole("button", { name: "적용" })).toBeDisabled();
  expect(await server.received("POST", "/edits")).toHaveLength(0);                                   // 화면이 먼저 막았다
  await form.getByLabel("끝", { exact: true }).fill("11:00");
  await expect(form.getByRole("alert")).toHaveCount(0);
  await form.getByRole("button", { name: "적용" }).click();
  await expect(toast(page, "1개 일정의 시간을 바꿨어요")).toBeVisible();
  const [edit] = await server.received("POST", "/edits");
  expect(edit.body).toEqual({ revision: 1, edits: [{ source_id: "s1", field: "items[0].ends_at", value: "11:00" }] });
  await expect(card(page, "경복궁 관람")).toContainText("변경 완료");
});

// ── 삭제는 보류 · 다시 제출 · 바뀐 곳 모아 보기 ──────────────────────────────────

test("삭제는 바로 지우지 않는다: 카드가 회색이 되고 휴지통 자리에 되돌리기가 서며, 서버로는 「다시 제출」을 누를 때 간다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await page.getByRole("button", { name: "올리브영 삭제" }).click();
  await expect(card(page, "올리브영")).toContainText("삭제 예정");
  await expect(page.getByRole("button", { name: "올리브영 삭제 되돌리기" })).toBeVisible();          // 휴지통이 있던 자리
  await expect(page.getByRole("button", { name: "올리브영 삭제", exact: true })).toHaveCount(0);
  expect(await server.received("POST", "/edits")).toHaveLength(0);                                   // 아직 아무것도 안 보냈다
  await expect(needsBadge(page)).toHaveCount(0);                                                     // 빼기로 한 일정은 「확인 필요」에서 빠진다(이동 하나는 남는다)
  await page.getByRole("button", { name: "올리브영 삭제 되돌리기" }).click();                          // 마음을 바꾸면 되돌린다
  await expect(card(page, "올리브영")).not.toContainText("삭제 예정");
  await page.getByRole("button", { name: "올리브영 삭제" }).click();
  await page.getByRole("button", { name: "다시 제출" }).click();                                      // 이때 서버로 간다
  await expect.poll(async () => (await server.received("POST", "/edits")).length).toBe(1);
  expect(JSON.stringify((await server.received("POST", "/edits"))[0].body)).toContain('.removed"');
  await expect.poll(async () => (await server.received("POST", "/revalidate")).length).toBe(1);
  await expect(card(page, "올리브영")).toHaveCount(0);
});

test("바뀐 곳은 파란색으로 강조되고, 머리의 「✎ 개수」를 누르면 바뀐 곳만 모아 보인다", async ({ page, request }) => {
  await openFinished(page, request);
  await expect(changedBadge(page)).toHaveCount(0);                                                   // 바뀐 곳이 없으면 표시도 없다
  await head(page, "올리브영").click();
  await card(page, "올리브영").getByRole("button", { name: "자동 추천" }).click();
  await expect(toast(page, "대체 후보 1순위로 바꿨어요")).toBeVisible();
  await expect(changedBadge(page)).toHaveText("✎1");
  await expect(page.locator("li[data-changed]")).toHaveCount(1);                                     // 강조된 카드
  await changedBadge(page).click();
  await expect(page.getByText("바뀐 곳만 보는 중이에요")).toBeVisible();
  await expect(card(page, "경복궁 관람")).toHaveCount(0);
  await expect(card(page, "올리브영 광화문점")).toBeVisible();
  await changedBadge(page).click();
  await expect(card(page, "경복궁 관람")).toBeVisible();
});

test("고친 게 있으면 「다시 제출」, 없고 확인할 것도 없으면 「여행 등록」 — 다시 제출하면 바뀐 부분만 확인 표시가 다시 켜지고 강조가 풀린다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await head(page, "올리브영").click();
  await card(page, "올리브영").getByRole("button", { name: "자동 추천" }).click();
  await expect(toast(page, "대체 후보 1순위로 바꿨어요")).toBeVisible();
  await expect(page.getByRole("button", { name: "다시 제출" })).toBeVisible();                        // 손으로 고친 것이 있다
  await expect(page.getByRole("button", { name: "여행 등록" })).toHaveCount(0);
  await page.getByRole("button", { name: "다시 제출" }).click();
  await expect(toast(page, "고친 내용을 다시 확인했어요")).toBeVisible();
  expect(await server.received("POST", "/revalidate")).toHaveLength(1);
  await expect(page.locator("li[data-changed]")).toHaveCount(0, { timeout: 15_000 });                // 다시 확인한 뒤에는 강조가 풀린다
  await expect(changedBadge(page)).toHaveCount(0);
});

// ── 수정안: 변경 전·후를 둘 다 들고 있다가 이어서 보여 준다 ─────────────────────────

test("계속 내리면: 안내가 수정안으로 이어지고, 제목이 「수정안」이 되며, 위로 올리면 변경 전 일정과 「계획 확인」이 다시 나온다 — 파란 안내 상자는 없다", async ({ page, request }) => {
  await openFinished(page, request);
  const hint = page.getByText("계속 내리면 권장 수정안이 반영된 모습을 보여 드려요");
  await expect(hint).toBeVisible();
  await expect(page.getByRole("heading", { name: "계획 확인" })).toBeVisible();
  await page.getByRole("button", { name: /^전체 자동 추천/ }).click();
  await expect(page.getByRole("heading", { name: "수정안" })).toBeVisible();                          // 수정안을 보는 동안의 제목
  await expect(page.getByRole("separator", { name: "여기부터 수정안" })).toBeAttached();
  await expect(page.getByText("계속 올리면 변경 전 일정이에요", { exact: false })).toBeAttached();
  await expect(page.getByRole("button", { name: "적용하기" })).toHaveCount(0);                         // 예전 안내 상자(적용하기·그대로 두기)는 없다
  await expect(page.getByRole("button", { name: "그대로 두기" })).toHaveCount(0);
  await expect(hint).toHaveCount(0);                                                                  // 아래로 밀어 본 뒤에는 그 안내 자리가 이어진 목록이다
  await expect(card(page, "올리브영 인사동점")).toBeVisible();                                         // 수정안의 바뀐 일정(서버가 고른 장소 이름이 카드 이름이 된다)
  await expect(page.getByText(/바뀜 · 이전/).first()).toBeVisible();
  await expect(changedBadge(page)).toHaveText("✎1");
  expect(await mockServer(request).received("POST", "/autofix")).toHaveLength(1);                     // 미리 보기일 뿐 — 저장하지 않았다
  await bodyOf(page).evaluate((element) => element.scrollTo({ top: 0 }));                              // 위로 올리면 변경 전
  await expect(page.getByRole("heading", { name: "계획 확인" })).toBeVisible();
  await expect(needsBadge(page)).toHaveText("!2");
  await expect(card(page, "올리브영")).toBeVisible();                                                  // 변경 전의 올리브영이 그대로 있다(수정안에서는 장소 이름이 카드 이름이다)
});

test("수정안을 보다가 「여행 등록」을 누르면 그 수정안을 저장한 뒤 바로 등록한다(적용하기를 따로 누르지 않는다)", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await page.getByRole("button", { name: /^전체 자동 추천/ }).click();
  await expect(page.getByRole("heading", { name: "수정안" })).toBeVisible();
  const register = page.getByRole("button", { name: "여행 등록" });
  await expect(register).not.toHaveAttribute("aria-disabled", "true");                                // 막지 않는다
  await register.click();
  await expect.poll(async () => (await server.received("POST", "/autofix")).length).toBe(2);          // 미리 보기 한 번 + 저장 한 번
  await expect.poll(async () => (await server.received("POST", "/confirm")).length).toBe(1);
  const [confirm] = await server.received("POST", "/confirm");
  expect(confirm.body).toMatchObject({ revision: 2 });                                                // 방금 저장한 판으로 등록했다
});

test("수정안을 보다가 일정을 직접 고치면 수정안이 먼저 저장되고 그 위에서 고친다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await page.getByRole("button", { name: /^전체 자동 추천/ }).click();
  await expect(page.getByRole("heading", { name: "수정안" })).toBeVisible();
  await page.getByRole("button", { name: /^경복궁 관람 시간 고치기/ }).last().click();
  const form = page.getByRole("form", { name: "경복궁 관람 시간 고치기" });
  await form.getByLabel("끝", { exact: true }).fill("11:00");
  await form.getByRole("button", { name: "적용" }).click();
  await expect(toast(page, "1개 일정의 시간을 바꿨어요")).toBeVisible();
  const autofix = await server.received("POST", "/autofix");
  expect(autofix.filter((entry) => !(entry.body as { dry_run?: boolean }).dry_run)).toHaveLength(1);    // 수정안 저장은 한 번(미리 보기 요청은 dry_run — 새 판을 미리 데워 두는 요청이 더 붙을 수 있다)
  const [edit] = await server.received("POST", "/edits");
  expect(edit.body).toMatchObject({ revision: 2 });                                                   // 저장된 수정안의 판 위에서 고쳤다
  await expect(page.getByRole("button", { name: "다시 제출" })).toBeVisible();                         // 손으로 고쳤으니 다시 제출
});

// ── 이동 경로선 · 핀 ───────────────────────────────────────────────────────────

test("접수 단계의 지도에도 이동 경로선이 그려진다: 길을 아는 구간은 실선, 직선으로 이은 구간은 점선, 출처와 이유는 목록 아래에 적는다", async ({ page, request }) => {
  await openFinished(page, request, undefined, { intakeRoutes: "on" });
  await expect(page.locator(".trip-route-line")).toHaveCount(2);
  await expect(page.locator(".trip-route-line--dashed")).toHaveCount(1);
  await head(page, "광장시장").scrollIntoViewIfNeeded();
  await expect(page.getByText("경로선: 지도 데이터 © OpenStreetMap contributors (ODbL)")).toBeVisible();
  await expect(page.getByText("점선은 길을 몰라 두 곳을 직선으로 이은 구간이에요.")).toBeVisible();
  await expect(page.getByText("경복궁 관람 → 올리브영: 탄 역 정보가 없어 직선으로 이었어요", { exact: false })).toBeVisible();
});

test("서버에 접수용 경로선이 없거나(404) 읽지 못해도(500) 핀은 그대로이고 오류 문구도 없다", async ({ page, request }) => {
  for (const intakeRoutes of ["off", "fail"]) {
    await mockServer(request).reset();
    await openFinished(page, request, undefined, { intakeRoutes });
    await expect(pin(page, "1. 경복궁 관람")).toBeVisible();
    await expect(page.locator(".trip-route-line")).toHaveCount(0);
    await expect(page.getByRole("alert").filter({ hasText: /경로|서버 오류/ })).toHaveCount(0);       // 선을 못 읽었다는 오류 문구는 없다(핀이 지도다)
  }
});

test("같은 자리에 있는 장소의 핀도 서로 겹치지 않는다(꼭짓점 방향을 달리해서 모두 보인다)", async ({ page, request }) => {
  await openFinished(page, request, (view) => {
    for (const item of view.review.items) item.place = { ...item.place, latitude: 37.5796, longitude: 126.977 };      // 셋 다 같은 좌표
  });
  const bodies = page.locator("[data-pin-body]");
  await expect(bodies).toHaveCount(3);
  const boxes = await bodies.evaluateAll((elements) => elements.map((element) => { const r = element.getBoundingClientRect(); return { left: r.left, top: r.top, right: r.right, bottom: r.bottom }; }));
  for (let one = 0; one < boxes.length; one += 1) for (let other = one + 1; other < boxes.length; other += 1) {
    const a = boxes[one], b = boxes[other];
    const overlap = Math.min(a.right, b.right) > Math.max(a.left, b.left) + 1 && Math.min(a.bottom, b.bottom) > Math.max(a.top, b.top) + 1;
    expect(overlap, `핀 ${one + 1} 과 ${other + 1} 이 겹친다`).toBe(false);
  }
  await expect(sheet(page)).toBeVisible();
});

test("지도에 「모든 일정 보기」 단추가 확대·축소 단추 옆에 있어, 확대하거나 옮긴 지도를 모든 핀이 보이는 처음 위치·배율로 되돌린다", async ({ page, request }) => {
  await openFinished(page, request);
  const first = pin(page, "1. 경복궁 관람");
  await expect(first).toBeVisible();
  const where = async () => { const box = (await first.boundingBox())!; return `${Math.round(box.x)},${Math.round(box.y)}`; };
  await expect.poll(async () => { const one = await where(); await page.waitForTimeout(500); return one === (await where()); }, { timeout: 10_000 }).toBe(true);   // 시트가 자리를 잡고 지도가 맞춰질 때까지(처음 위치는 그 뒤에 잰다)
  const before = (await first.boundingBox())!;
  const map = page.getByRole("region", { name: "여행 지도" });
  await map.hover({ position: { x: 200, y: 100 } });                                              // 단추는 지도에 포인터가 있을 때 보인다
  const zoom = page.locator(".leaflet-control-zoom");
  await expect(zoom.getByRole("button", { name: "모든 일정 보기" })).toBeVisible();                   // 확대·축소와 같은 묶음 안
  await zoom.getByRole("button", { name: "Zoom in" }).click();
  await zoom.getByRole("button", { name: "Zoom in" }).click();
  await expect.poll(async () => Math.abs((await first.boundingBox())!.x - before.x)).toBeGreaterThan(20);   // 확대하니 핀이 제자리에서 멀어졌다
  await zoom.getByRole("button", { name: "모든 일정 보기" }).click();
  await expect.poll(async () => { const now = (await first.boundingBox())!; return Math.abs(now.x - before.x) + Math.abs(now.y - before.y); }, { timeout: 8_000 }).toBeLessThan(4);   // 처음 자리로
  for (const label of ["2. 올리브영", "3. 광장시장"]) await expect(pin(page, label)).toBeInViewport();                 // 모든 핀이 보인다
});

// ── 2026-10-04 사용자 지시: 시간 끌기 · 입력 · 밀기 · 여유 간격 · 되돌리기 · 시간 초기화 ──────────────────────────────────────────────

/** 시간 편집기를 연다(광장시장 12:30–13:30: 앞 올리브영 11:00–12:00 에서 이동 16분 → 12:16 이전으로는 못 당긴다). */
async function openTime(page: Page, title: string) {
  await page.getByRole("button", { name: new RegExp(`^${title} 시간 고치기`) }).click();
  return page.getByRole("form", { name: `${title} 시간 고치기` });
}
const editsOf = async (server: ReturnType<typeof mockServer>) => (await server.received("POST", "/edits")).map((entry) => entry.body as { revision: number; edits: { field: string; value: unknown }[] });
const fieldsOf = (body: { edits: { field: string; value: unknown }[] }) => Object.fromEntries(body.edits.map((edit) => [edit.field, edit.value]));

test("일정 사이 간격은 비는 시간만큼 벌어지고, 15분 넘게 비면 「여유 N분」을 한 번 연하게 적는다", async ({ page, request }) => {
  await openFinished(page, request);
  await expect(page.getByText("여유 21분")).toBeVisible();                                            // 경복궁 → 올리브영: 11:00 − (10:30 + 이동 9분) = 21분
  await expect(page.getByText(/^여유 /)).toHaveCount(1);                                              // 올리브영 → 광장시장은 14분이라 말은 없다(간격만)
  const spaces = await page.locator("p[class*=free]").evaluateAll((elements) => elements.map((element) => Math.round(element.getBoundingClientRect().height)));
  expect(spaces[0]).toBeGreaterThanOrEqual(15);                                                        // 21분이면 기본 간격(14px)에 더해 19px 가량 더 벌어진다
});

test("시간 편집기에 시각을 적으면 밀리는 일정이 미리 보이고, 적용하면 모든 일정이 요청 하나로 간다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  const form = await openTime(page, "광장시장");
  await expect(form.getByText("가능한 시각 02:55 ~ 23:00")).toBeVisible();                              // 앞 일정들을 하루 맨 앞까지 밀 수 있는 만큼
  await form.getByLabel("시작", { exact: true }).fill("11:30");                                                          // 앞 올리브영(12:00 끝)과 겹치니 앞 일정들이 밀린다
  await expect(form.getByRole("status")).toContainText("함께 바뀌는 일정 2개");
  await expect(form.getByRole("status")).toContainText("올리브영");
  await expect(page.getByRole("button", { name: /^광장시장 시간 고치기 · 지금 11:30/ })).toBeVisible();       // 목록이 미리 보인다
  expect(await server.received("POST", "/edits")).toHaveLength(0);                                     // 아직 서버로 가지 않았다
  await form.getByRole("button", { name: "적용" }).click();
  await expect(toast(page, "3개 일정의 시간을 바꿨어요")).toBeVisible();
  const bodies = await editsOf(server);
  expect(bodies).toHaveLength(1);                                                                      // 요청 하나
  const fields = fieldsOf(bodies[0]);
  expect(fields["items[2].starts_at"]).toBe("11:30");
  expect(fields["items[2].ends_at"]).toBe("12:30");                                                    // 수행 시간 60분은 그대로
  expect(fields["items[1].starts_at"]).toBe("10:14");                                                  // 올리브영이 밀려 올라갔다(12:30 − … )
  expect(fields["items[0].starts_at"]).toBeDefined();
});

test("「앞뒤 일정도 함께 밀기」를 끄면 자기 앞뒤 여유 안에서만 입력할 수 있고, 벗어나면 이유와 범위를 말한다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  const form = await openTime(page, "광장시장");
  await form.getByLabel("앞뒤 일정도 함께 밀기").uncheck();
  await expect(form.getByText("가능한 시각 12:16 ~ 23:00")).toBeVisible();                              // 앞 일정 끝(12:00) + 이동 16분
  await form.getByLabel("시작", { exact: true }).fill("12:10");
  await expect(form.getByRole("alert")).toContainText("가능한 시각은 12:16 ~ 23:00이에요");
  await expect(form.getByRole("button", { name: "적용" })).toBeDisabled();
  await form.getByLabel("시작", { exact: true }).fill("12:20");
  await expect(form.getByRole("alert")).toHaveCount(0);
  await form.getByRole("button", { name: "적용" }).click();
  await expect(toast(page, "1개 일정의 시간을 바꿨어요")).toBeVisible();
  expect(fieldsOf((await editsOf(server))[0])).toEqual({ "items[2].starts_at": "12:20", "items[2].ends_at": "13:20" });
});

test("−5분 · +5분 단추는 시작을 5분씩 옮기고, 범위 끝에서 멈춘다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  const form = await openTime(page, "광장시장");
  await form.getByLabel("앞뒤 일정도 함께 밀기").uncheck();
  await form.getByRole("button", { name: "+5분" }).click();
  await form.getByRole("button", { name: "+5분" }).click();
  await expect(form.getByLabel("시작", { exact: true })).toHaveValue("12:40");
  await expect(form.getByLabel("끝", { exact: true })).toHaveValue("13:40");                              // 끝 칸도 같은 만큼 따라가 머무는 시간(60분)이 그대로다
  for (let at = 0; at < 6; at += 1) await form.getByRole("button", { name: "−5분" }).click();           // 12:10 을 지나 12:16 에서 멈춘다
  await expect(form.getByLabel("시작", { exact: true })).toHaveValue("12:16");
  await form.getByRole("button", { name: "+5분" }).click();
  await form.getByRole("button", { name: "적용" }).click();
  await expect.poll(async () => (await editsOf(server)).length).toBe(1);
  expect(fieldsOf((await editsOf(server))[0])["items[2].starts_at"]).toBe("12:21");
});

test("끌개를 아래로 끌면 시작이 늦어지고(10px = 5분) 손을 떼면 바로 적용된다 — 위로 끌면 일찍, 범위 밖은 끝에서 멈춘다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  const form = await openTime(page, "광장시장");
  await form.getByLabel("앞뒤 일정도 함께 밀기").uncheck();
  const grip = form.getByRole("button", { name: /끌어서 시작 시각 바꾸기/ });
  const box = (await grip.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2 + 40, { steps: 6 });             // 40px = 20분
  await expect(form.getByLabel("시작", { exact: true })).toHaveValue("12:50");                                           // 끄는 동안 미리 보인다
  await expect(form.getByLabel("끝", { exact: true })).toHaveValue("13:50");
  expect(await server.received("POST", "/edits")).toHaveLength(0);
  await page.mouse.up();
  await expect(toast(page, "1개 일정의 시간을 바꿨어요")).toBeVisible();
  expect(fieldsOf((await editsOf(server))[0])["items[2].starts_at"]).toBe("12:50");

  const again = await openTime(page, "광장시장");
  await again.getByLabel("앞뒤 일정도 함께 밀기").uncheck();
  const grip2 = again.getByRole("button", { name: /끌어서 시작 시각 바꾸기/ });
  const box2 = (await grip2.boundingBox())!;
  await page.mouse.move(box2.x + box2.width / 2, box2.y + box2.height / 2);
  await page.mouse.down();
  await page.mouse.move(box2.x + box2.width / 2, box2.y + box2.height / 2 - 400, { steps: 8 });         // 한참 위로: 12:16 에서 멈춘다
  await expect(again.getByLabel("시작", { exact: true })).toHaveValue("12:16");
  await page.mouse.up();
});

test("잠근 일정은 시간이 못 움직이는 벽이다: 그 일정에 막혀 앞으로는 더 못 당긴다", async ({ page, request }) => {
  await openFinished(page, request);
  await page.getByRole("button", { name: "경복궁 관람 꼭 넣을 일정으로 고정" }).click();
  await expect(page.getByRole("button", { name: "경복궁 관람 고정 풀기" })).toBeVisible();
  const form = await openTime(page, "올리브영");
  await expect(form.getByText("가능한 시각 10:39 ~ ")).toBeVisible();                                    // 잠근 경복궁(10:30 끝) + 이동 9분 아래로는 못 당긴다
  await page.getByRole("button", { name: /^경복궁 관람 시간 고치기/ }).click({ force: true });
  await expect(toast(page, "고정한 일정이라 바꿀 수 없어요")).toBeVisible();
});

test("바꾼 시간에는 「되돌리기」가 붙고(수정·삭제 앞), 누르면 그 일정만 처음 시간으로 돌아오며, 머리의 「시간 초기화」는 바꾼 시간 모두를 한 번에 되돌린다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  const form = await openTime(page, "광장시장");
  await form.getByLabel("시작", { exact: true }).fill("11:30");
  await form.getByRole("button", { name: "적용" }).click();
  await expect(toast(page, "3개 일정의 시간을 바꿨어요")).toBeVisible();
  const undo = page.getByRole("button", { name: "광장시장 시간 되돌리기" });
  await expect(undo).toBeVisible();
  await expect(page.getByRole("button", { name: "경복궁 관람 시간 되돌리기" })).toBeVisible();          // 함께 밀린 일정에도 붙는다
  const reset = page.getByRole("button", { name: /^시간 조정 3곳 모두 처음으로/ });
  await expect(reset).toBeVisible();
  const before = (await editsOf(server)).length;
  await reset.click();
  await expect.poll(async () => (await editsOf(server)).length).toBe(before + 1);                       // 요청 하나
  const back = fieldsOf((await editsOf(server)).at(-1)!);
  expect(back["items[2].starts_at"]).toBe("12:30");
  expect(back["items[1].starts_at"]).toBe("11:00");
  expect(back["items[0].starts_at"]).toBe("09:00");
  await expect(undo).toHaveCount(0);                                                                    // 처음 시간이 되면 표시가 없다
  await expect(reset).toHaveCount(0);
});
