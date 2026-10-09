import { expect, test, type Page } from "@playwright/test";
import { mockServer } from "./helpers";
import { mapSettled, openFinished, pin } from "./plan-check-kit";

/**
 * `[2026-10-05 사용자 선택 — 지도 단추 · 거리 눈금 · 가장자리 마커 안 B · 첫 지도 시점 안 C]` 계획 확인 화면의 지도(무료 지도 · Leaflet 빌드). mock 서버 시험이다 — 화면 반응만 본다
 * (구글·네이버 SDK 로는 확인하지 못했다: `maps.spec.ts` 의 SDK 계약 대역이 단추 없이도 도는지만 본다).
 *   - 단추: ＋ · 거리 눈금 · － · 모든 일정 보기 (위치 동의가 없으면 「내 위치」 단추는 말도 없다), 접으면 탭 하나만 남고 접은 상태는 기억된다.
 *   - 가장자리 마커: 화면 밖의 일정은 가장자리에 거리 칩으로 서고, 누르면 그곳으로 가며 그 일정이 골라진다.
 */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const group = (page: Page) => page.getByRole("group", { name: "지도 단추" });
const map = (page: Page) => page.getByRole("region", { name: "여행 지도" });
const wake = async (page: Page) => {
  await map(page).hover({ position: { x: 150, y: 150 } });
  const open = group(page).getByRole("button", { name: "지도 단추 펼치기" });
  if (await open.count() && await group(page).getAttribute("data-layout") !== "tab") await open.click();
};
const scale = (page: Page) => group(page).getByRole("img", { name: /^거리 눈금/ });
const chips = (page: Page) => page.locator("[data-edge-chip]");

test("접기 단추에 거리가 함께 나오고 확대·축소·모든 일정 보기 순서로 선다", async ({ page, request }) => {
  await page.setViewportSize({ width: 1280, height: 1100 });                                          // 지도가 충분히 높아 세로로 선다
  await openFinished(page, request);
  await wake(page);
  const names = await group(page).getByRole("button").evaluateAll((buttons) => buttons.map((button) => button.getAttribute("aria-label")));
  expect(names).toEqual(["지도 단추 접기", "확대", "축소", "모든 일정 보기"]);
  await expect(group(page).getByRole("button", { name: /내 위치/ })).toHaveCount(0);
  const [plus, ruler, minus] = await Promise.all([group(page).getByRole("button", { name: "확대" }), scale(page), group(page).getByRole("button", { name: "축소" })].map((item) => item.boundingBox()));
  expect(ruler!.y).toBeLessThan(plus!.y);
  expect(plus!.y).toBeLessThan(minus!.y);
  await expect(group(page).getByRole("button", { name: "지도 단추 접기" }).getByRole("img", { name: /^거리 눈금/ })).toBeVisible();
  await expect(group(page).locator('[class*=scaleBar]')).toHaveCount(0);
});

test("거리 눈금은 지도에 담긴 거리를 말하고, 확대하면 더 짧은 거리로 바뀐다", async ({ page, request }) => {
  await openFinished(page, request);
  await wake(page);
  await expect(scale(page)).toBeVisible();
  const label = async () => ((await scale(page).getAttribute("aria-label")) ?? "").replace("거리 눈금 ", "");
  const meters = (text: string) => (text.endsWith("km") ? Number.parseFloat(text) * 1000 : Number.parseFloat(text));
  // 처음 맞추는 동안(시트가 자리를 잡고 지도가 모든 핀에 맞춰지는 동안)에는 눈금이 바뀐다 — 가라앉은 뒤에 잰다
  await expect.poll(async () => { const one = await label(); await page.waitForTimeout(700); return one === (await label()); }, { timeout: 10_000 }).toBe(true);
  const before = await label();
  expect(before).toMatch(/^\d+(m|km)$/);
  await group(page).getByRole("button", { name: "확대" }).click();
  await group(page).getByRole("button", { name: "확대" }).click();
  await expect.poll(async () => meters(await label())).toBeLessThan(meters(before));                  // 두 단계 확대: 같은 폭이 더 짧은 거리다
});

test("접으면 눈금과 탭이 남고 다시 열어도 기본은 접힌 상태다", async ({ page, request }) => {
  await openFinished(page, request);
  await wake(page);
  await group(page).getByRole("button", { name: "지도 단추 접기" }).click();
  await expect(group(page).getByRole("button", { name: "확대" })).toHaveCount(0);
  await expect(group(page).getByRole("button", { name: "지도 단추 펼치기" })).toBeVisible();
  await page.reload();
  await expect(needsBadgeOrSheet(page)).toBeVisible();
  await expect(group(page).getByRole("button", { name: "지도 단추 펼치기" })).toBeVisible();          // 다시 열어도 접혀 있다
  await mapSettled(page);
  const intro = page.getByRole("status").filter({ hasText: "계획 확인 화면이에요" });
  if (await intro.count()) await intro.getByRole("button", { name: "닫기", exact: true }).click();
  await expect(map(page)).not.toHaveAttribute("data-moving", "true");
  await group(page).getByRole("button", { name: "지도 단추 펼치기" }).click();
  await expect(group(page).getByRole("button", { name: "확대" })).toBeVisible();
});

test("목록 창을 크게 열어 지도가 낮아지면 같은 단추가 가로 한 줄로 서고, 더 낮으면 접는 탭만 남는다", async ({ page, request }) => {
  await page.setViewportSize({ width: 1280, height: 1100 });
  await openFinished(page, request);
  await wake(page);
  const layout = () => group(page).getAttribute("data-layout");
  const folded = () => group(page).getAttribute("data-folded");
  const state = async () => `${await layout()}/${await folded()}`;
  await expect.poll(state).toBe("column/null");                                                      // 지도가 높을 때: 세로로
  const handle = page.getByRole("button", { name: "목록 높이 바꾸기" });
  await handle.focus();
  for (let press = 0; press < 5; press += 1) await page.keyboard.press("ArrowUp");                   // 목록 창을 한 번에 40px 씩 키운다: 지도가 낮아진다
  await wake(page);
  await expect.poll(state).toMatch(/^(row\/null|column\/true)$/);                                    // 가로 한 줄, 또는 (아주 낮으면) 접는 탭만 — 세로로 남아 있지 않다
  if ((await layout()) === "row") {
    const [first, last] = await Promise.all([group(page).getByRole("button", { name: "확대" }), group(page).getByRole("button", { name: "모든 일정 보기" })].map((item) => item.boundingBox()));
    expect(Math.abs(first!.y - last!.y)).toBeLessThan(2);                                            // 같은 줄이다
  }
});

test("지도를 확대하면 화면 밖으로 나간 일정이 가장자리에 「번호 · 거리」 칩으로 서고, 누르면 그 일정으로 가며 골라진다", async ({ page, request }) => {
  await openFinished(page, request);
  await expect(chips(page)).toHaveCount(0);                                                          // 모든 핀이 보이는 처음에는 없다
  await wake(page);
  for (let step = 0; step < 3; step += 1) { await group(page).getByRole("button", { name: "확대" }).click(); await page.waitForTimeout(450); }
  await expect.poll(async () => chips(page).count()).toBeGreaterThan(0);
  const chip = chips(page).first();
  await expect(chip).toContainText(/\d/);
  await expect(chip).toContainText(/\d+(m|km)$/);                                                    // 거리
  const label = (await chip.getAttribute("aria-label")) ?? "";
  expect(label).toMatch(/화면 밖에 있어요/);
  const number = /^(\d+)/.exec(label)?.[1];
  await chip.click();
  await expect(page.locator(`.leaflet-marker-icon[title^="${number}."]`)).toBeInViewport({ timeout: 8_000 });   // 눌렀더니 그 핀이 화면에 들어왔다
});

test("멀리 끌어 핀이 모두 화면 밖이면 칩 하나가 모두를 담아 서고(「2 · 3 · 4」), 지도 층(타일 · 핀 층) 위에 그려지고, 가장자리에서 잘리지 않는다", async ({ page, request }) => {
  // `[2026-10-07 사용자 지적 — 일정 이상 멀어지면 마커가 아예 사라진다]` 실제 지도 타일이 뜨면 Leaflet 층(z-index 200~800)이 칩 · 단추(z-index 4) 위에 그려져 칩이 지도 뒤에 숨었다. 시험은 타일이 없어 못 잡았다 →
  // 지도 층처럼 높은 z-index 의 판을 하나 얹어 놓고도 칩이 그 위에서 눌리는지(= 쌓임 맥락이 갈렸는지) 본다.
  await page.setViewportSize({ width: 560, height: 880 });
  await openFinished(page, request);
  const region = (await map(page).boundingBox())!;
  for (let at = 0; at < 4; at += 1) {
    await page.mouse.move(region.x + 300, region.y + 380);
    await page.mouse.down();
    await page.mouse.move(region.x + 60, region.y + 380, { steps: 8 });
    await page.mouse.up();
    await page.waitForTimeout(250);
  }
  await expect(chips(page)).toHaveCount(1);                                                           // 같은 쪽에 있는 핀 셋은 하나로 묶인다
  const chip = chips(page).first();
  await expect(chip).toContainText("1 · 2 · 3");
  await page.evaluate(() => {
    const pane = document.createElement("div");
    pane.id = "fake-leaflet-pane";
    pane.style.cssText = "position:absolute;inset:0;z-index:400;background:rgba(0,200,0,.2)";             // Leaflet 의 타일 층(.leaflet-map-pane)이 가진 z-index
    document.querySelector(".leaflet-container")!.append(pane);
  });
  const onTop = await chip.evaluate((element) => {
    const box = element.getBoundingClientRect();
    return element.contains(document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2));
  });
  expect(onTop).toBe(true);
  // 칩은 지도 안에 통째로 들어 있다(여러 번호를 담아 넓어도 가장자리에서 잘리지 않는다)
  const inside = (await chip.boundingBox())!;
  expect(inside.x).toBeGreaterThanOrEqual(region.x - 0.5);
  expect(inside.x + inside.width).toBeLessThanOrEqual(region.x + region.width + 0.5);
  await page.evaluate(() => document.getElementById("fake-leaflet-pane")?.remove());
});

test("일정이 있는 날을 처음 보여 줄 때 첫 일정의 핀이 한 번 두근거린다 (고리가 퍼졌다 사라진다)", async ({ page, request }) => {
  await openFinished(page, request, undefined, {}, false);
  const first = pin(page, "1. 경복궁 관람");
  await expect(first.locator("[data-pin-pulse]")).toHaveCount(1, { timeout: 10_000 });
  await expect(first.locator("[data-pin-pulse]")).toHaveCount(0, { timeout: 6_000 });                 // 두 번 퍼지고 사라진다(남지 않는다)
});

/** 계획 확인 화면이 떠 있다는 신호(시트의 머리). */
function needsBadgeOrSheet(page: Page) {
  return page.getByRole("region", { name: /장소·운영시간 확인|계획 확인|수정안|등록 완료/ });
}
