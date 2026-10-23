import { expect, test, type Page } from "@playwright/test";
import { mockServer } from "./helpers";
import { openFinished, sheet } from "./plan-check-kit";

/**
 * `[2026-10-06 사용자 지적 — 여행 일정 창 확대·축소가 부드럽지 않다]` 일정 창(시트)의 높이는 한 번에 바뀌고(안의 글이 움직이는 도중 다시 배치되지 않는다) 창은 compositor 위의 transform 으로 미끄러져 간다.
 * 끌 때는 상태가 아니라 화면에 바로 써서(움직일 때마다 이 화면 전체를 다시 그리지 않는다) 손을 떼면 닿은 높이로 남는다. 테스트용 mock 서버로 도는 자동 시험이다(화면 반응 — 실서버 확인 아님).
 */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const handle = (page: Page) => page.getByRole("button", { name: "목록 높이 바꾸기" });
const layoutHeight = (page: Page) => sheet(page).evaluate((element) => (element as HTMLElement).offsetHeight);
/** The sliding transforms running on the sheet right now. */
const slides = (page: Page) => sheet(page).evaluate((element) => element.getAnimations().filter((animation) => {
  const effect = animation.effect as KeyframeEffect | null;
  return effect?.getKeyframes().some((frame) => "transform" in frame && frame.transform && frame.transform !== "none") && animation.playState === "running" && effect?.getTiming().duration === 380;
}).length);

test("손잡이를 누르면 높이는 바로 바뀌고 창은 transform 으로 미끄러져 간다(380ms) — 다 끝나면 아무 움직임도 남지 않는다", async ({ page, request }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await openFinished(page, request);
  const before = await layoutHeight(page);
  await handle(page).click();                                                                           // 중간 → 크게
  const after = await layoutHeight(page);
  expect(after).toBeGreaterThan(before + 40);
  await expect.poll(() => slides(page), { timeout: 400 }).toBeGreaterThan(0);                             // 미끄러지는 중이다
  await expect.poll(() => slides(page), { timeout: 2000 }).toBe(0);                                      // 끝났다
  expect(await layoutHeight(page)).toBe(after);                                                          // 높이는 그대로(애니메이션이 높이를 건드리지 않았다)
});

test("끌 때는 손을 뗄 때까지 미끄러지는 움직임이 없고 따라오며, 놓으면 닿은 높이로 남는다(놓은 뒤 다시 미끄러지지 않는다)", async ({ page, request }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await openFinished(page, request);
  const start = await layoutHeight(page);
  const box = (await handle(page).boundingBox())!;
  const x = box.x + box.width / 2, y = box.y + 10;
  await page.mouse.move(x, y);
  await page.mouse.down();
  for (let step = 1; step <= 20; step += 1) await page.mouse.move(x, y - step * 4);                       // 80px 위로
  await expect.poll(() => layoutHeight(page), { timeout: 2000 }).toBeGreaterThanOrEqual(start + 70);
  expect(await slides(page)).toBe(0);                                                                    // 끄는 동안 미끄러지는 움직임은 없다
  const held = await layoutHeight(page);
  await page.mouse.up();
  await page.waitForTimeout(150);
  expect(await slides(page)).toBe(0);                                                                    // 놓은 뒤에도 없다
  expect(Math.abs((await layoutHeight(page)) - held)).toBeLessThanOrEqual(1);                            // 닿은 높이로 남는다
});

test("높이를 줄일 때 창 아래에 지도가 비쳐 보이는 틈이 없다 — 창 밑을 같은 색이 채운다", async ({ page, request }) => {
  await openFinished(page, request);
  const fill = await sheet(page).evaluate((element) => { const style = getComputedStyle(element, "::after"); return { top: style.top, height: style.height, position: style.position }; });
  expect(fill.position).toBe("absolute");
  expect(parseFloat(fill.height)).toBeGreaterThan(300);
});
