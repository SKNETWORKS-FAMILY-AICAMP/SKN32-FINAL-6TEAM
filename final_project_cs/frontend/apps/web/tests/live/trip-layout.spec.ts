import { expect, test } from "@playwright/test";
import { agree, mockServer, noHorizontalScroll, registerStubTrip, useKorean } from "./helpers";

// The trip screen's data and chat are in `trip.spec.ts`; this keeps the layout checks the old demo suite held.
test.beforeEach(async ({ page, request }) => { await mockServer(request).reset(); await useKorean(page); await agree(page); });

test("375px와 320px에서 하단 탭으로 일정·지도·채팅을 바꾸고 가로로 넘치지 않으며, 빈 메시지는 막는다", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await registerStubTrip(page);
  for (const width of [375, 320]) {
    await page.setViewportSize({ width, height: 812 });
    for (const [label, id] of [["일정", "schedule"], ["지도", "map"], ["채팅", "chat"]]) {
      const button = page.getByRole("button", { name: label, exact: true });
      await button.click();
      await expect(button).toHaveAttribute("aria-pressed", "true");
      await expect(page.locator(`#trip-pane-${id}`)).toBeVisible();
      for (const other of ["schedule", "map", "chat"].filter((item) => item !== id)) await expect(page.locator(`#trip-pane-${other}`)).toBeHidden();
      await noHorizontalScroll(page);
    }
  }
  await page.getByRole("button", { name: "메시지 전송" }).click();
  await expect(page.locator("#main-content").getByRole("alert")).toContainText("메시지를 입력해 주세요.");
});

test("일차·일정·지도 선택이 이어진다: 일정을 펼쳐 「지도에서 보기」를 누르면 그 핀이 선택되고, 핀의 「일정 상세 보기」가 그 일정을 펼친다", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await registerStubTrip(page);
  const timeline = page.locator("#trip-pane-schedule");
  const map = page.locator("#trip-pane-map");
  const stop = timeline.getByRole("button", { name: /경복궁 관람/ });
  await stop.click();
  await expect(stop).toHaveAttribute("aria-expanded", "true");
  await expect(timeline.locator("dl")).toContainText("다음 일정12:00 · 점심 식당");
  await timeline.getByRole("button", { name: "지도에서 보기" }).click();
  await expect(map).toBeVisible();
  await expect(timeline).toBeHidden();
  const pin = map.locator('.leaflet-marker-icon[title^="2. 경복궁 관람"]');
  await expect(pin).toHaveAttribute("aria-pressed", "true");

  await map.locator('.leaflet-marker-icon[title^="3. 점심 식당"]').dispatchEvent("click");     // 지도가 움직이는 동안은 .click() 의 「안정됨」 확인이 밀려서 click 이벤트를 직접 보낸다
  await expect(map.getByRole("heading", { name: "점심 식당" })).toBeVisible();
  await map.getByRole("button", { name: "일정 상세 보기" }).click();
  const lunch = timeline.getByRole("button", { name: /점심 식당/ });
  await expect(lunch).toHaveAttribute("aria-expanded", "true");
  await expect(lunch).toBeFocused();
  await expect(timeline.locator('article[data-selected="true"]')).toContainText("점심 식당");

  await page.getByRole("button", { name: /2일차/ }).click();
  await expect(timeline.getByRole("heading", { name: "2일차 일정" })).toBeVisible();
  await expect(timeline.getByRole("button", { name: /경복궁 관람/ })).toHaveCount(0);
});
