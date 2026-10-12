import { expect, test } from "@playwright/test";
import { mockServer, paneTab, start, TRIP_ID } from "./helpers";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

test("scrollend 이벤트가 없는 브라우저에서도 소개 카드 드래그 뒤 스냅이 복원된다", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 812 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  // 구형 브라우저처럼 scrollend만 전달하지 않습니다. scroll/pointer 이벤트는 그대로입니다.
  await page.addInitScript(() => {
    const add = EventTarget.prototype.addEventListener;
    EventTarget.prototype.addEventListener = function (type, listener, options) {
      if (type === "scrollend") return;
      return add.call(this, type, listener, options);
    };
  });
  await start(page);
  await page.goto("/");
  await page.getByRole("button", { name: "다음 화면", exact: true }).first().click();
  const guide = page.getByRole("region", { name: "triPilot 이용 방법", exact: true });
  const track = guide.getByRole("group", { name: "1 / 4", exact: true }).locator("..");
  await expect.poll(() => page.locator("main").evaluate(main => Math.abs(main.scrollTop - (main.children[1] as HTMLElement).offsetTop))).toBeLessThan(2);
  const box = (await track.boundingBox())!;
  const x = box.x + box.width / 2, y = box.y + box.height / 2;
  await page.mouse.move(x, y); await page.mouse.down();
  await page.mouse.move(x - 150, y, { steps: 8 }); await page.mouse.up();
  await expect(guide.getByText("2 / 4", { exact: true })).toBeVisible();
  await expect.poll(() => track.evaluate(element => getComputedStyle(element).scrollSnapType)).toBe("x mandatory");
});

test("여행 화면의 작은 목록에서는 채팅 내용 조각이 그려지지 않는다", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await start(page);
  await page.goto(`/trips/${TRIP_ID}`);
  await paneTab(page, "채팅").click();
  const handle = page.getByRole("button", { name: "목록 높이 바꾸기", exact: true });
  await handle.focus();
  for (let i = 0; i < 14; i += 1) await page.keyboard.press("ArrowDown");
  await expect(page.locator("[data-sheet]")).toHaveAttribute("data-compact", "true");
  const section = page.getByRole("region", { name: "일정 목록", exact: true });
  const evidence = await section.evaluate(root => {
    const sheet = root.getBoundingClientRect();
    const chat = root.querySelector<HTMLElement>("#trip-pane-chat")!;
    const text = [...chat.querySelectorAll<HTMLElement>("p,strong,button,span")].filter(node => {
      const box = node.getBoundingClientRect();
      const left = Math.max(sheet.left, box.left), right = Math.min(sheet.right, box.right);
      const top = Math.max(sheet.top, box.top), bottom = Math.min(sheet.bottom, box.bottom);
      if (right - left < 2 || bottom - top < 2 || !node.textContent?.trim()) return false;
      const hit = document.elementFromPoint((left + right) / 2, (top + bottom) / 2);
      return Boolean(hit && (node.contains(hit) || hit.contains(node)));
    }).map(node => ({ text: node.textContent?.trim(), box: node.getBoundingClientRect().toJSON() }));
    return { sheet: sheet.toJSON(), chat: chat.getBoundingClientRect().toJSON(), text };
  });
  await test.info().attach("compact-trip-paint-evidence", { body: JSON.stringify(evidence), contentType: "application/json" });
  await page.screenshot({ path: test.info().outputPath("compact-trip-chat.png") });
  expect(evidence.text, JSON.stringify(evidence)).toEqual([]);
});
