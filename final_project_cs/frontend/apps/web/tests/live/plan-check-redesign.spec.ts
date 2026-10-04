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

test("카드 왼쪽의 시간을 누르면 그 자리에서 시작·끝 시각을 고치고, 고친 값만 서버로 간다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  await page.getByRole("button", { name: /^경복궁 관람 시간 고치기/ }).click();
  const form = page.getByRole("form", { name: "경복궁 관람 시간 고치기" });
  await form.getByLabel("끝").fill("08:00");                                                         // 시작(09:00)보다 빠르다
  await form.getByRole("button", { name: "저장" }).click();
  await expect(form.getByRole("alert")).toHaveText("끝 시각이 시작보다 빨라요.");
  expect(await server.received("POST", "/edits")).toHaveLength(0);                                   // 화면이 먼저 막았다
  await form.getByLabel("끝").fill("11:00");
  await form.getByRole("button", { name: "저장" }).click();
  await expect(toast(page, "시간을 바꿨어요")).toBeVisible();
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
  await form.getByLabel("끝").fill("11:00");
  await form.getByRole("button", { name: "저장" }).click();
  await expect(toast(page, "시간을 바꿨어요")).toBeVisible();
  expect(await server.received("POST", "/autofix")).toHaveLength(2);                                  // 미리 보기 + 저장
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
