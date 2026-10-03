import { expect, test, type Page } from "@playwright/test";
import { noHorizontalScroll, useKorean } from "./helpers/app";

/**
 * The plan-check screen on its preview page (`/preview/plan-check`) — the mockup's example data and example rules
 * (`preview-engine.ts`), not a server. The scenarios follow the mockup `mockups/tripilot-plan-check-streaming.html`:
 * 1 reading and checking · 2 the result · 3 recommend · 4 the change screen · 5 lock · 6 delete · 7 recommend all →
 * check again → register. The backend wires the real route; these tests hold the screen's own behaviour.
 */
test.beforeEach(async ({ page }) => { await useKorean(page); });

const sheet = (page: Page) => page.getByRole("region", { name: /장소·운영시간 확인|계획 확인|등록 완료/ });
const card = (page: Page, name: string) => page.getByRole("article", { name, exact: true });
const head = (page: Page, name: string) => card(page, name).getByRole("heading").getByRole("button");
const toast = (page: Page, text: string) => page.getByRole("status").filter({ hasText: text });
/** A button that cannot act stays pressable to say why (`aria-disabled`); Playwright will not press it unless forced. */
const pressOff = (page: Page, name: string | RegExp) => page.getByRole("button", { name }).first().click({ force: true });

async function result(page: Page) {
  await page.goto("/preview/plan-check");
  await page.getByRole("button", { name: "결과 바로 보기" }).click();
  await expect(page.getByRole("heading", { name: "10월 서울 여행", level: 1 })).toBeVisible();
}

test("1 · 원문을 한 줄씩 읽고, 지도 위 시트에서 장소·이동을 하나씩 확인한 뒤, 카드가 접히고 여행 제목으로 끝난다", async ({ page }) => {
  await page.goto("/preview/plan-check");
  await expect(page.getByText("미리보기 · 예시 데이터 · 서버 미연결")).toBeVisible();
  await expect(page.getByRole("heading", { name: "계획을 확인하고 있어요", level: 1 })).toBeVisible();

  // ①② Lines are read one at a time; each read line says what it became.
  await expect(page.getByText("→ 1일차 11:00 · 올리브영")).toBeVisible();
  await expect(page.getByText("찾은 일정 4개")).toBeVisible();

  // ③ Map and sheet: the counts know the whole (4 places, 2 moves) before every card is shown.
  await expect(sheet(page).getByRole("heading", { name: "장소·운영시간 확인" })).toBeVisible();
  await expect(sheet(page).getByText(/장소 \d\/4 · 이동 \d\/2/)).toBeVisible();
  await expect(card(page, "경복궁").getByText("관광공사 정보로 찾았어요")).toBeVisible();

  // ④ Done: the title replaces the bar, the cards fold, what needs a look is counted and marked.
  await expect(page.getByRole("heading", { name: "10월 서울 여행", level: 1 })).toBeVisible({ timeout: 25_000 });
  await expect(sheet(page).getByText("장소 1곳 · 이동 1구간 확인 필요")).toBeVisible();
  await expect(card(page, "올리브영").getByText("확인 필요")).toBeVisible();
  await expect(card(page, "광장시장").getByText("조정")).toBeVisible();
  await expect(card(page, "경복궁").getByText("유지")).toBeVisible();
  await expect(card(page, "경복궁").getByText("관광공사 정보로 찾았어요")).toHaveCount(0);
  await expect(page.getByText("위치 미정 · 올리브영")).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "확인을 마쳤어요." })).toBeAttached();
});

test("움직임 줄이기 설정이면 다시 그리지 않고 서버 결과를 바로 보인다", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/preview/plan-check");
  // The example's last snapshot comes at 1.5 s; drawn at once, it is there well before the paced replay (about 12 s) would end.
  await expect(page.getByRole("heading", { name: "10월 서울 여행", level: 1 })).toBeVisible({ timeout: 4_000 });
  await expect(sheet(page).getByText("장소 1곳 · 이동 1구간 확인 필요")).toBeVisible();
});

test("「결과 바로 보기」는 다시 재생하지 않고 결과를 그리고, 「처음부터 재생」은 읽기 화면부터 다시 한다", async ({ page }) => {
  await result(page);
  await expect(page.getByRole("progressbar")).toHaveCount(0);           // the title has replaced the bar
  await page.getByRole("button", { name: "처음부터 재생" }).click();
  await expect(page.getByRole("progressbar", { name: "계획 확인 진행" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "계획을 확인하고 있어요", level: 1 })).toBeVisible();
});

test("뒤로 가기는 계획 입력 화면으로 간다", async ({ page }) => {
  await page.goto("/preview/plan-check");
  await page.getByRole("button", { name: "뒤로" }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
});

test("PC 기기 틀·375px·320px에서 읽기 화면·결과·바꾸기 화면이 가로로 넘치지 않는다", async ({ page }) => {
  for (const [width, height] of [[1280, 900], [375, 812], [320, 640]]) {
    await page.setViewportSize({ width, height });
    await page.goto("/preview/plan-check");
    await expect(page.getByText("찾은 일정")).toBeVisible();
    await noHorizontalScroll(page);
    await page.getByRole("button", { name: "결과 바로 보기" }).click();
    await expect(page.getByRole("heading", { name: "10월 서울 여행", level: 1 })).toBeVisible();
    await noHorizontalScroll(page);
    await card(page, "올리브영").scrollIntoViewIfNeeded();
    await expect(card(page, "올리브영")).toBeInViewport({ ratio: 0.5 });
    await page.getByRole("button", { name: "올리브영 수정" }).click();
    await expect(page.getByRole("heading", { name: "올리브영 바꾸기" })).toBeVisible();
    await noHorizontalScroll(page);                                     // the cards swipe inside their own row
  }
});

test("2 · 결과: 카드는 하나씩 펼쳐지고, 카드를 고르면 지도의 그 핀이 선택되며, 핀을 누르면 그 카드가 펼쳐진다", async ({ page }) => {
  await result(page);
  await expect(head(page, "경복궁")).toHaveAttribute("aria-expanded", "false");
  await head(page, "경복궁").click();
  await expect(head(page, "경복궁")).toHaveAttribute("aria-expanded", "true");
  await expect(card(page, "경복궁").getByText("관광공사 정보로 찾았어요")).toBeVisible();
  await head(page, "광장시장").click();
  await expect(head(page, "광장시장")).toHaveAttribute("aria-expanded", "true");
  await expect(head(page, "경복궁")).toHaveAttribute("aria-expanded", "false");                 // one card open at a time
  await expect(page.getByRole("button", { name: "3. 광장시장" })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "1. 경복궁" }).click();                          // the pin opens its card
  await expect(head(page, "경복궁")).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByRole("button", { name: "1. 경복궁" })).toHaveAttribute("aria-pressed", "true");
});

test("2 · 결과: 일차 머리를 누르면 지도가 그 날로 바뀌고, 손잡이는 시트를 높게·낮게·중간으로 돌린다", async ({ page }) => {
  await result(page);
  const day2 = page.getByRole("button", { name: /^2일차/ });
  await expect(page.getByRole("button", { name: "1. 경복궁" })).toBeVisible();
  await day2.click();
  await expect(day2).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: "1. N서울타워" })).toBeVisible();
  await expect(page.getByRole("button", { name: "1. 경복궁" })).toHaveCount(0);
  const screen = page.locator("[data-sheet]");
  await expect(screen).toHaveAttribute("data-sheet", "half");
  const handle = page.getByRole("button", { name: "목록 높이 바꾸기" });
  await handle.click();
  await expect(screen).toHaveAttribute("data-sheet", "full");
  await handle.click();
  await expect(screen).toHaveAttribute("data-sheet", "peek");
  await handle.click();
  await expect(screen).toHaveAttribute("data-sheet", "half");
});

test("2 · 결과: 이동 줄을 누르면 경로·수단·도착 검사가 펼쳐진다", async ({ page }) => {
  await result(page);
  const move = page.getByRole("button", { name: /도보.*12분 · 0\.8km/ });
  await expect(move).toHaveAttribute("aria-expanded", "false");
  await move.click();
  await expect(move).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByText("올리브영 지점이 미정이라 가장 가까운 광화문점 기준이에요")).toBeVisible();
});

test("3 · 자동 추천: 카드가 1순위를 알려 주고, 누르면 그곳으로 바뀌어 다시 확인되며, 「되돌리기」로 되돌린다", async ({ page }) => {
  await result(page);
  await head(page, "올리브영").click();
  await expect(card(page, "올리브영").getByText("자동 추천은 1순위 올리브영 광화문점으로 바로 바꿔요")).toBeVisible();
  await card(page, "올리브영").getByRole("button", { name: "자동 추천" }).click();
  await expect(toast(page, "올리브영을 올리브영 광화문점으로 바꿨어요")).toBeVisible();
  await expect(card(page, "올리브영 광화문점")).toBeVisible();
  await expect(card(page, "올리브영 광화문점").getByText("대체 후보 1순위 · 카카오 정보로 찾았어요")).toBeVisible();
  // The branch is found, but the walk from 경복궁 (until 11:30) still reaches it late: the move needs a look now.
  await expect(sheet(page).getByText("이동 1구간 확인 필요")).toBeVisible();
  await toast(page, "올리브영을 올리브영 광화문점으로 바꿨어요").getByRole("button", { name: "되돌리기" }).click();
  await expect(toast(page, "되돌렸어요")).toBeVisible();
  await expect(card(page, "올리브영")).toBeVisible();
  await expect(sheet(page).getByText("장소 1곳 · 이동 1구간 확인 필요")).toBeVisible();
});

test("4 · 수정 화면: 지금 일정과 후보 A·B·C를 넘기면 지도의 핀이 따라가고, 사진과 검색 결과에서 고른 곳으로 바꾼다", async ({ page }) => {
  await result(page);
  await page.getByRole("button", { name: "올리브영 수정" }).click();
  await expect(page.getByRole("heading", { name: "올리브영 바꾸기" })).toBeVisible();
  await expect(page.getByText("지금 일정 · 1/4")).toBeVisible();
  await expect(page.getByText("옆으로 넘기면 다른 후보 3곳 →")).toBeVisible();
  // The map: the day's other stops greyed (not pressable), the alternatives A · B · C.
  await expect(page.getByRole("button", { name: "A. 올리브영 광화문점" })).toBeVisible();
  await expect(page.getByRole("button", { name: "1. 경복궁" })).toHaveCount(0);

  await page.getByRole("button", { name: "후보 A" }).click();
  await expect(page.getByText("대체 후보 A · 2/4")).toBeVisible();
  await expect(page.getByRole("button", { name: "A. 올리브영 광화문점" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("heading", { name: /등록된 사진 · 올리브영 광화문점/ })).toBeVisible();
  await page.getByRole("button", { name: "C. 올리브영 종각역점" }).click();                       // a pin brings its card
  await expect(page.getByText("대체 후보 C · 4/4")).toBeVisible();
  await page.getByRole("button", { name: /시트를 위로 올리면 올리브영 종각역점 사진 6장/ }).click();
  await expect(page.locator("[data-sheet]")).toHaveAttribute("data-sheet", "full");

  // Search: the top bar finds places; one picked becomes a card to change to.
  await page.getByRole("searchbox", { name: "장소 검색" }).fill("명동");
  await expect(page.getByText("‘명동’ 검색 결과 1곳")).toBeVisible();
  await page.getByRole("button", { name: /올리브영 명동 플래그십/ }).click();
  await expect(page.getByText("검색으로 고른 곳 · 2/5")).toBeVisible();
  await page.getByRole("article", { name: "올리브영 명동 플래그십" }).getByRole("button", { name: "이 장소로 바꾸기" }).click();
  await expect(toast(page, "올리브영을 올리브영 명동 플래그십으로 바꿨어요")).toBeVisible();
  await expect(page.getByRole("heading", { name: "올리브영 바꾸기" })).toHaveCount(0);
  await expect(card(page, "올리브영 명동 플래그십").getByText("검색으로 고른 곳 · 카카오 정보로 찾았어요")).toBeVisible();
});

test("4 · 수정 화면의 「직접 고치기」: 끝이 시작보다 빠르거나 장소가 비면 보내지 않고, 「바꾸기 그만두기」는 수정 단추로 돌아간다", async ({ page }) => {
  await result(page);
  await page.getByRole("button", { name: "광장시장 수정" }).click();
  await page.getByText("직접 고치기 · 이름·날짜·시각·장소 없음").click();
  const editor = page.getByRole("form", { name: "「광장시장」 고치기" });
  await editor.getByLabel("끝").fill("12:00");
  await editor.getByRole("button", { name: "저장" }).click();
  await expect(editor.getByRole("alert")).toHaveText("끝 시각이 시작보다 빨라요.");
  await editor.getByLabel("끝").fill("13:30");
  await editor.getByRole("searchbox", { name: "장소 이름" }).fill("");
  await editor.getByRole("button", { name: "저장" }).click();
  await expect(editor.getByRole("alert")).toHaveText("장소 이름을 적거나 「장소 없음」을 골라 주세요.");
  await editor.getByRole("button", { name: "취소" }).click();
  await expect(editor).toHaveCount(0);
  await page.getByRole("button", { name: "바꾸기 그만두기" }).click();
  await expect(page.getByRole("heading", { name: "광장시장 바꾸기" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "광장시장 수정" })).toBeFocused();
});

test("4 · 「직접 고치기」에서 「장소 없음」으로 저장하면 카드가 「조정」이 되고 위치 미정으로 보인다", async ({ page }) => {
  await result(page);
  await page.getByRole("button", { name: "경복궁 수정" }).click();
  await page.getByText("직접 고치기 · 이름·날짜·시각·장소 없음").click();
  const editor = page.getByRole("form", { name: "「경복궁」 고치기" });
  await editor.getByLabel("장소 없음(자유 시간 등)").check();
  await editor.getByRole("button", { name: "저장" }).click();
  await expect(toast(page, "저장했어요.")).toBeVisible();
  await expect(card(page, "경복궁").getByText("조정")).toBeVisible();
  await expect(page.getByText(/위치 미정 · .*경복궁/)).toBeVisible();
});

test("5 · 잠금: 고정한 일정은 수정·자동 추천·삭제가 막히고 이유를 말하며, 확인 필요 일정은 고정할 수 없다", async ({ page }) => {
  await result(page);
  const lock = page.getByRole("button", { name: "경복궁 꼭 넣을 일정으로 고정" });
  await lock.click();
  await expect(toast(page, "경복궁을 꼭 넣을 일정으로 고정했어요")).toBeVisible();
  await expect(page.getByRole("button", { name: "경복궁 고정 풀기" })).toHaveAttribute("aria-pressed", "true");
  await pressOff(page, "경복궁 수정");
  await expect(toast(page, "고정한 일정이라 바꿀 수 없어요")).toBeVisible();
  await expect(page.getByRole("heading", { name: "경복궁 바꾸기" })).toHaveCount(0);
  await pressOff(page, "경복궁 삭제");
  await expect(toast(page, "고정한 일정은 삭제할 수 없어요")).toBeVisible();
  await expect(page.getByRole("alertdialog")).toHaveCount(0);
  await pressOff(page, "확인이 필요한 일정은 고정할 수 없어요");
  await expect(toast(page, "확인이 필요한 일정은 먼저 고쳐야 고정할 수 있어요")).toBeVisible();
});

test("6 · 삭제: 확인창(Tab은 두 단추 안, 바깥 누르면 닫힘, 320px) → 삭제하면 앞뒤 이동을 다시 계산하고 「되돌리기」로 되돌린다", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 });
  await result(page);
  await page.getByRole("button", { name: "올리브영 삭제" }).click();
  const dialog = page.getByRole("alertdialog", { name: "올리브영 일정을 삭제하시겠습니까?" });
  await expect(dialog).toBeInViewport();
  await expect(dialog).toContainText("삭제한 뒤 잠시 「되돌리기」로 되돌릴 수 있습니다.");
  await noHorizontalScroll(page);
  await expect(dialog.getByRole("button", { name: "취소" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(dialog.getByRole("button", { name: "삭제" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(dialog.getByRole("button", { name: "취소" })).toBeFocused();
  await page.mouse.click(5, 300);
  await expect(dialog).toHaveCount(0);
  await page.getByRole("button", { name: "올리브영 삭제" }).click();
  await dialog.getByRole("button", { name: "삭제" }).click();
  await expect(card(page, "올리브영")).toHaveCount(0);
  await expect(toast(page, "올리브영 일정을 삭제했어요")).toContainText("앞뒤 이동을 다시 계산했어요");
  await expect(page.getByRole("button", { name: /지하철.*약 \d+분 · 2\.\dkm/ })).toBeVisible();          // 경복궁 → 광장시장, worked out again
  await toast(page, "올리브영 일정을 삭제했어요").getByRole("button", { name: "되돌리기" }).click();
  await expect(card(page, "올리브영")).toBeVisible();
});

test("7 · 꺼진 「재검증」은 이유를 말하고, 「전체 자동 추천」 → 「재검증」 → 「여행 등록」 → 「등록 완료」로 간다", async ({ page }) => {
  await result(page);
  const auto = page.getByRole("button", { name: /전체 자동 추천/ });
  await expect(auto).toContainText("2");
  await pressOff(page, "재검증");
  await expect(toast(page, "확인이 필요한 항목 2건이 남아 있어요")).toBeVisible();

  await auto.click();
  await expect(toast(page, "검증된 대체 일정으로 바꿨어요")).toContainText("올리브영 → 올리브영");
  await expect(sheet(page).getByText("고친 곳이 있어요 · 재검증해 주세요")).toBeVisible();
  const recheck = page.getByRole("button", { name: "재검증" });
  await expect(recheck).not.toHaveAttribute("aria-disabled", "true");
  await recheck.click();
  await expect(sheet(page).getByText(/재검증 중 · \d\/4/)).toBeVisible();
  await expect(toast(page, "재검증을 통과했어요")).toBeVisible({ timeout: 10_000 });
  await expect(sheet(page).getByText("고칠 곳이 없어요")).toBeVisible();
  await page.getByRole("button", { name: "여행 등록" }).click();
  await expect(page.getByRole("link", { name: "등록 완료 — 여행 보기" })).toBeVisible();
  await expect(sheet(page).getByRole("heading", { name: "등록 완료" })).toBeVisible();
  // Registered: the screen's tools close and say so.
  await pressOff(page, /.* 수정$/);
  await expect(toast(page, "이미 등록한 여행이에요")).toBeVisible();
});
