import { expect, test, type Page } from "@playwright/test";
import { mockServer } from "./helpers";
import { openFinished, timeBox, toast, turnWheel } from "./plan-check-kit";

/**
 * `[2026-10-21 사용자 결정 — ST4F-702]` 시간 고치기 A 휠 · 손가락 꾹 눌러 잡기. 손가락은 크롬 개발 도구의 터치 흉내(CDP `Input.dispatchTouchEvent`)다 — 휴대폰 실기기 · 진동은 따로 본다.
 * mock 서버 시험이다 — 화면 반응만 본다. 장면: 경복궁 09:00–10:30 → 이동 9분 → 올리브영 11:00–12:00 → 이동 16분 → 광장시장 12:30–13:30.
 */
test.use({ hasTouch: true });
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const editsOf = async (server: ReturnType<typeof mockServer>) => (await server.received("POST", "/edits")).map((entry) => entry.body as { edits: { field: string; value: unknown }[] });
const fieldsOf = (body: { edits: { field: string; value: unknown }[] }) => Object.fromEntries(body.edits.map((edit) => [edit.field, edit.value]));
const timeButton = (page: Page, title: string) => page.getByRole("button", { name: new RegExp(`^${title} 시간 고치기`) });
const rowOf = (page: Page, title: string) => timeButton(page, title).locator("xpath=ancestor::li[1]");

/** 손가락 하나(터치 흉내). */
async function finger(page: Page) {
  const cdp = await page.context().newCDPSession(page);
  return (type: "touchStart" | "touchMove" | "touchEnd" | "touchCancel", x = 0, y = 0) =>
    cdp.send("Input.dispatchTouchEvent", { type, touchPoints: type === "touchEnd" || type === "touchCancel" ? [] : [{ x, y, id: 1 }] });
}
/** 원의 가운데. `centre`: 먼저 그 줄을 목록 가운데로 옮긴다(목록 끝 가까이에서 끌면 목록이 저절로 흐른다 — 그것은 따로 본다). */
async function dotOf(page: Page, title: string, centre = true) {
  const dot = rowOf(page, title).locator("span[data-grab]");
  if (centre) {
    await dot.evaluate((element) => element.closest("li")!.scrollIntoView({ block: "center" }));
    await page.waitForTimeout(300);
  }
  const box = (await dot.boundingBox())!;
  return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
}

test("손가락이 원을 스치고 지나가면(꾹 누르지 않고 바로 움직이면) 잡히지 않고 시간도 그대로다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  const touch = await finger(page);
  const { x, y } = await dotOf(page, "올리브영");
  await touch("touchStart", x, y);
  for (let step = 1; step <= 6; step += 1) await touch("touchMove", x, y - step * 8);              // 0.45초 전에 8px 넘게 움직였다 — 스크롤하는 손가락
  await touch("touchEnd");
  await expect(rowOf(page, "올리브영")).not.toHaveAttribute("data-time-press", /.*/);
  await expect(page.getByRole("button", { name: /^올리브영 시간 고치기 · 지금 11:00/ })).toBeVisible();
  await expect(page.locator('[data-overlay="time"]')).toHaveCount(0);
  expect(await server.received("POST", "/edits")).toHaveLength(0);
});

test("꾹 누르면(0.45초) 원이 잡히고 말풍선이 뜨며, 끌면 원이 손가락을 따라가고(5분 = 6px) 놓으면 한 번에 저장된다", async ({ page, request }) => {
  const server = await openFinished(page, request);
  const touch = await finger(page);
  const row = rowOf(page, "광장시장");
  const { x, y } = await dotOf(page, "광장시장");
  await touch("touchStart", x, y);
  await expect(row).toHaveAttribute("data-time-press", "pressing");                               // 누르는 동안 — 원 둘레가 찬다
  await expect(row).toHaveAttribute("data-time-press", "held", { timeout: 2000 });                // 다 차면 잡힌다
  await expect(row.locator("[class*=holdBubble]")).toHaveText("12:30");
  for (let step = 1; step <= 4; step += 1) await touch("touchMove", x, y + step * 6);              // 24px = 20분(목록 축척 1분 = 1.2px)
  await expect(page.getByRole("button", { name: /^광장시장 시간 고치기 · 지금 12:50/ })).toBeVisible();
  await expect(row.locator("[class*=holdBubble]")).toContainText("12:50");
  await expect(row.locator("[class*=holdBubble]")).toContainText("+20분");
  const moved = await dotOf(page, "광장시장", false);
  expect(Math.abs(moved.y - (y + 24))).toBeLessThan(4);                                           // ★잡힌 원이 손가락 밑에 있다(2026-10-21 사용자 확인 — 손가락에서 빠지던 것)
  expect(await server.received("POST", "/edits")).toHaveLength(0);                                // 끄는 동안은 아무것도 안 보낸다
  await touch("touchEnd");
  await expect(toast(page, "1개 일정의 시간을 바꿨어요")).toBeVisible();
  expect(fieldsOf((await editsOf(server))[0])["items[2].starts_at"]).toBe("12:50");
  await expect(row).not.toHaveAttribute("data-time-press", /.*/);
});

test("휠 카드를 열면 시트가 크게 올라가고, 닫으면 원래 높이로 돌아온다 — 휠로 고른 시각은 칸에 「오후 12:35」로 보인다", async ({ page, request }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openFinished(page, request);
  const sheet = page.locator("[data-sheet]");
  await expect(sheet).toHaveAttribute("data-sheet", "half");
  await timeButton(page, "광장시장").click();
  const form = page.getByRole("form", { name: "광장시장 시간 고치기" });
  await expect(sheet).toHaveAttribute("data-sheet", "full");
  await expect(form.getByRole("button", { name: "적용" })).toBeInViewport();                      // 카드 아래 ✕ · ✓ 까지 보인다
  await turnWheel(form, "분", 1);
  await expect(timeBox(form, "시작")).toContainText("오후 12:35");
  await form.getByRole("button", { name: "취소" }).click();
  await expect(form).toHaveCount(0);
  await expect(sheet).toHaveAttribute("data-sheet", "half");
});
