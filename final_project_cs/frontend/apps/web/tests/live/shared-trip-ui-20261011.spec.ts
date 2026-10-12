import { expect, test, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { dayTab, mockServer, noHorizontalScroll, paneTab, start, TRIP_ID, tripScreen } from "./helpers";
import { openFinished } from "./plan-check-kit";

const shots = "mockups/registered-trip-parity-2026-10-11-v1";
async function finger(page: Page, type: string, x: number, id: number) {
  await page.locator("#trip-pane-schedule > div").evaluate((el, input) => el.dispatchEvent(new PointerEvent(input.type, {
    bubbles: true, cancelable: true, pointerId: input.id, pointerType: "touch", isPrimary: input.id === 1,
    clientX: input.x, clientY: 600, button: 0, buttons: input.type === "pointerup" ? 0 : 1,
  })), { type, x, id });
}
async function aligned(page: Page) {
  await expect.poll(() => page.getByRole("tablist", { name: "일차 고르기", includeHidden: true }).evaluate(strip => {
    const tab = strip.querySelector<HTMLElement>('[aria-selected="true"]');
    const marker = strip.querySelector<HTMLElement>('[class*="dayMarker"]');
    if (!tab || !marker) return Infinity;
    const a = tab.getBoundingClientRect(), b = marker.getBoundingClientRect();
    return Math.max(Math.abs(a.left - b.left), Math.abs(a.right - b.right), Math.abs(a.top - b.top));
  })).toBeLessThan(1);
}
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });
for (const width of [375, 1280]) {
  test(`등록 여행은 검증 날짜·테두리·스크롤 규칙을 공유한다 ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 812 });
    await start(page); await page.goto(`/trips/${TRIP_ID}`); await expect(tripScreen(page)).toBeVisible();
    await aligned(page);
    const strip = page.getByRole("tablist", { name: "일차 고르기", includeHidden: true });
    const body = page.locator("#trip-pane-schedule > div");
    await expect(page.locator("#trip-card-i-a")).toHaveCSS("border-top-color", "rgba(0, 0, 0, 0)");
    await dayTab(page, /^2일차/).click(); await aligned(page);
    await paneTab(page, "채팅").click(); await paneTab(page, "일정").click(); await aligned(page);
    await body.evaluate(el => { el.scrollTop = 100; });
    await expect(strip).toHaveAttribute("data-quiet", "true");
    await body.evaluate(el => { el.scrollTop = 0; });
    await expect(strip).not.toHaveAttribute("data-quiet");
    await dayTab(page, /^1일차/).click(); await aligned(page);
    await finger(page, "pointerdown", 140, 1); await finger(page, "pointerdown", 260, 2);
    await finger(page, "pointermove", 130, 1); await finger(page, "pointermove", 290, 2);
    await finger(page, "pointerup", 130, 1); await finger(page, "pointerup", 290, 2);
    await expect.poll(() => page.evaluate(() => localStorage.getItem("triPilot.planListZoom"))).toBe("1.3");
    await finger(page, "pointerdown", 150, 1); await finger(page, "pointerdown", 250, 2);
    await finger(page, "pointermove", 190, 1); await finger(page, "pointermove", 210, 2);
    await finger(page, "pointerup", 190, 1); await finger(page, "pointerup", 210, 2);
    await expect(dayTab(page, /^전체$/)).toHaveAttribute("aria-selected", "true");
    await finger(page, "pointerdown", 190, 1); await finger(page, "pointerdown", 210, 2);
    await finger(page, "pointermove", 100, 1); await finger(page, "pointermove", 300, 2);
    await finger(page, "pointerup", 100, 1); await finger(page, "pointerup", 300, 2);
    await expect(dayTab(page, /^1일차/)).toHaveAttribute("aria-selected", "true"); await aligned(page);
    await noHorizontalScroll(page);
    await mkdir(shots, { recursive: true }); await page.screenshot({ path: `${shots}/shared-${width}.png` });
  });
  test(`수정안 전환은 휠 꼬리를 막고 새 스크롤과 일정 추가를 허용한다 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    await openFinished(page, request, undefined, { intakeEvents: "off" });
    const body = page.locator("div[class*=sheetBody]");
    await body.evaluate(el => { el.scrollTop = el.scrollHeight; });
    await body.evaluate(el => {
      const observer = new MutationObserver(() => {
        if (!document.querySelector('button[aria-current="step"][aria-label="2. 수정안"]')) return;
        observer.disconnect();
        el.setAttribute("data-test-tail-cancelled", String(!el.dispatchEvent(new WheelEvent("wheel", { deltaY: 600, bubbles: true, cancelable: true }))));
      });
      observer.observe(document, { subtree: true, attributes: true, childList: true });
    });
    await page.getByRole("button", { name: /아래로 스크롤하면.*수정안/ }).click();
    await expect(page.getByRole("button", { name: "2. 수정안", exact: true })).toHaveAttribute("aria-current", "step");
    await expect.poll(() => body.evaluate(el => el.scrollTop)).toBeLessThan(2);
    // 전환 직후 같은 휠 동작은 새 페이지를 내리지 않는다. 취소 가능한 DOM 입력도 확인한다.
    await expect(body).toHaveAttribute("data-test-tail-cancelled", "true");
    await expect.poll(() => body.evaluate(el => el.scrollTop)).toBeLessThan(2);
    await page.waitForTimeout(450);
    await body.hover({ position: { x: 40, y: 150 } }); await page.mouse.wheel(0, 160);
    await expect.poll(() => body.evaluate(el => el.scrollTop)).toBeGreaterThan(5);
    await body.evaluate(el => { el.scrollTop = 0; });
    const add = body.locator('[data-insert-near] button[id^="plan-insert-"]');
    await expect(add).toBeVisible();
    await add.click();
    await expect(page.getByRole("region", { name: "일정 추가 화면", exact: true })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "일정 이름", exact: true })).toBeVisible();
    const writes = (await mockServer(request).log()).filter(row => row.method === "POST" && /autofix/.test(row.path));
    expect(writes.some(row => row.body?.dry_run === true)).toBe(true);
    expect(writes.some(row => row.body?.dry_run !== true)).toBe(true);
    await page.getByRole("button", { name: "취소", exact: true }).click();
    await expect(body.locator('[data-insert-near] button[id^="plan-insert-"]')).toBeVisible();
  });
  test(`채팅은 이전 대화를 유지하고 최신 이동·새 답변·직접 전송을 지원한다 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    await mockServer(request).scenario({ bell: "on" });
    let extra = false;
    await page.route(`**/v1/web/trips/${TRIP_ID}/chat?*`, async route => {
      const response = await route.fetch();
      const turns = Array.from({ length: 28 }, (_, index) => ({ role: index % 2 ? "assistant" : "customer", case_id: `old-${index}`, at: "2026-10-01T08:00:00Z", text: `${index + 1}번째 여행 대화입니다. ${"장소와 이동시간을 살펴봅니다. ".repeat(4)}` }));
      if (extra) turns.push({ role: "assistant", case_id: "new-answer", at: "2026-10-01T09:00:00Z", text: "새로 도착한 여행 안내입니다." });
      await route.fulfill({ response, json: { trip_id: TRIP_ID, turns } });
    });
    await start(page); await page.goto(`/trips/${TRIP_ID}`); await paneTab(page, "채팅").click();
    const log = page.getByRole("log", { name: "여행 대화 이력" });
    const end = () => log.evaluate(el => el.scrollHeight - el.clientHeight - el.scrollTop);
    await expect.poll(end).toBeLessThan(2);
    await log.evaluate(el => { el.scrollTop = 100; });
    const latest = page.getByRole("button", { name: "최신 대화로 이동", exact: true });
    await expect(latest).toBeVisible();
    const before = await log.evaluate(el => el.scrollTop);
    extra = true; await mockServer(request).ring(["trip"]);
    await expect(page.getByRole("button", { name: "새 메시지 · 최신 대화로 이동", exact: true })).toBeVisible();
    expect(Math.abs(await log.evaluate(el => el.scrollTop) - before)).toBeLessThan(2);
    const jump = page.getByRole("button", { name: "새 메시지 · 최신 대화로 이동", exact: true });
    await jump.focus(); await page.keyboard.press("Enter");
    await expect.poll(end).toBeLessThan(2); await expect(log).toBeFocused();
    await log.evaluate(el => { el.scrollTop = 100; }); await expect(latest).toBeVisible();
    await page.getByRole("textbox", { name: "여행 메시지", exact: true }).fill("다음 일정 알려 주세요");
    await page.getByRole("button", { name: "메시지 전송", exact: true }).click();
    await expect.poll(end).toBeLessThan(2);
    await noHorizontalScroll(page);
    await page.screenshot({ path: `${shots}/chat-${width}.png` });
  });
}
