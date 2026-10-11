import { expect, test } from "@playwright/test";
import { agree, mockServer, noHorizontalScroll, paneTab, registerStubTrip, tripScreen, useKorean } from "./helpers";

// The trip screen's data and chat are in `trip.spec.ts`; this keeps the layout checks.
// `[2026-10-07 사용자 결정 — 목업 C안]` The trip is the plan check's screen: the map with the sheet over it, 「일정 | 채팅」 in the sheet's head, the chat bar at the bottom.
test.beforeEach(async ({ page, request }) => { await mockServer(request).reset(); await useKorean(page); await agree(page); });

test("375px와 320px에서 지도 위 시트의 「일정 | 채팅」으로 칸을 바꾸고 가로로 넘치지 않으며, 빈 메시지는 막는다", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await registerStubTrip(page);
  await expect(page.locator("main .leaflet-container")).toBeVisible();                       // 지도는 늘 시트 뒤에 있다
  for (const width of [375, 320]) {
    await page.setViewportSize({ width, height: 812 });
    for (const [label, id] of [["일정", "schedule"], ["채팅", "chat"]] as const) {
      const tab = paneTab(page, label);
      await tab.click();
      await expect(tab).toHaveAttribute("aria-selected", "true");
      await expect(page.locator(`#trip-pane-${id}`)).not.toHaveAttribute("inert");
      await expect(page.locator(`#trip-pane-${id === "chat" ? "schedule" : "chat"}`)).toHaveAttribute("inert", "");
      await noHorizontalScroll(page);
    }
  }
  await page.getByRole("button", { name: "메시지 전송" }).click();
  await expect(page.locator("#main-content").getByRole("alert")).toContainText("메시지를 입력해 주세요.");
});

test("채팅 버튼은 막대만 펼치고(입력칸에 초점 없음), 입력칸에 초점이 가면 채팅 칸으로 넘어간다 — 일정 칸으로 돌아오면 쓰던 글은 막대에 남는다", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await registerStubTrip(page);
  await page.getByRole("button", { name: "채팅 입력 열기" }).click();
  const input = page.locator("#trip-chat-message");
  await expect(input).toBeVisible();
  await expect(input).not.toBeFocused();
  await expect(page.getByRole("button", { name: "채팅 막대 접기" })).toBeFocused();
  await expect(paneTab(page, "일정")).toHaveAttribute("aria-selected", "true");
  await input.click();
  await expect(paneTab(page, "채팅")).toHaveAttribute("aria-selected", "true");
  await expect(input).toBeFocused();
  await input.fill("쓰던 질문");
  await input.press("Escape");                                                                 // 채팅 칸 → 일정 칸
  await expect(paneTab(page, "일정")).toHaveAttribute("aria-selected", "true");
  await expect(input).toHaveValue("쓰던 질문");
  await page.getByRole("button", { name: "채팅 막대 접기" }).click();
  await expect(page.getByRole("button", { name: "채팅 입력 열기" })).toBeFocused();
});

test("일차·일정·지도 선택이 이어진다: 일정을 펼쳐 「지도에서 보기」를 누르면 그 핀이 선택되고 알림 막대가 그 일정을 말하며, 핀을 누르면 그 일정이 목록에서 펼쳐진다", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await registerStubTrip(page);
  const timeline = tripScreen(page);
  const map = page.locator("main .leaflet-container");
  const stop = page.locator("#stop-button-i-b");
  await stop.click();
  await expect(stop).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator("#stop-detail-i-b dl")).toContainText("다음 일정12:00 · 점심 식당");
  await page.locator("#stop-detail-i-b").getByRole("button", { name: "지도에서 보기" }).click();
  await expect(map.locator('.leaflet-marker-icon[title^="2. 경복궁 관람"]')).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("status").filter({ hasText: "경복궁 관람" }).first()).toBeAttached();

  await map.locator('.leaflet-marker-icon[title^="3. 점심 식당"]').dispatchEvent("click");     // 지도가 움직이는 동안은 .click() 의 「안정됨」 확인이 밀려서 click 이벤트를 직접 보낸다
  await expect(page.locator("#stop-button-i-c")).toHaveAttribute("aria-expanded", "true");
  await expect(timeline.locator('li[data-selected="true"]')).toContainText("점심 식당");

  await page.getByRole("tab", { name: /2일차/ }).click();
  await expect(timeline.getByRole("heading", { name: /2일차/ })).toBeVisible();
  await expect(page.locator("#stop-button-i-b")).toHaveCount(0);
});
