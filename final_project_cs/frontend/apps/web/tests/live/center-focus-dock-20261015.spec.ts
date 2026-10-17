import { expect, test, type Page } from "@playwright/test";
import { agree, beforeTheTrip, mockServer, openPane, registerStubTrip, useKorean } from "./helpers";
import { openFinished } from "./plan-check-kit";

// `[2026-10-15 사용자 결정 — ST4F-532 · ST4F-493]` 목업(개인 저장소 2026-10-15 세 화면)의 「제안」: 접힌 카드의 회색 테두리는 끄고, ＋ 와 같은 가운데 기준으로 상자 하나(카드 또는 이동 칸)에만
// 회색 테두리를 두른다(`use-center-focus.ts`). 등록한 여행의 채팅 칸에서는 입력 막대가 바닥 · 폭 가득으로 붙는다(A안 — 막대 안 둥근 입력칸).

const focused = (page: Page) => page.locator("[data-focus]");
const strong = (page: Page) => page.evaluate(() => {
  const probe = document.createElement("i");
  probe.style.color = "var(--color-border-strong)";
  document.body.append(probe);
  const color = getComputedStyle(probe).color;
  probe.remove();
  return color;
});

test("계획 확인: 접힌 카드는 테두리가 없고 가운데 상자 하나만 회색 테두리 — 맨 위는 첫 상자, 맨 끝은 마지막 상자", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 640 });            // 목록이 스크롤되게(모방 서버 일정은 카드 셋 — keep · 확인 필요 · 조정됨)
  await page.emulateMedia({ reducedMotion: "reduce" });
  await openFinished(page, request, undefined, { intakeEvents: "off" });
  await expect(focused(page)).toHaveCount(1);
  const grey = await strong(page);
  await expect(focused(page)).toHaveCSS("border-top-color", grey);
  const boxes = page.locator('li[data-type="item"]:not([data-past]) article, li[data-type="move"]:not([data-past]) [data-rail-box]');
  await expect(boxes.first()).toHaveAttribute("data-focus", "");
  // 회색은 초점 하나뿐 — 「확인 필요」 · 「조정됨」 카드는 제 색이다
  const others = await page.locator('li[data-type="item"] article:not([data-focus])').evaluateAll((cards) => cards.map((card) => getComputedStyle(card).borderTopColor));
  expect(others.length).toBeGreaterThan(0);
  expect(others).not.toContain(grey);
  await page.locator("div[class*=sheetBody]").evaluate((body) => { body.scrollTop = body.scrollHeight; });
  await expect(boxes.last()).toHaveAttribute("data-focus", "");
  await expect(focused(page)).toHaveCount(1);
  // 초점이 떠난 접힌 카드(keep)는 테두리가 없다(10-13 의 회색 테두리를 뺐다)
  await expect(page.locator('li[data-type="item"][data-verdict="keep"] article')).toHaveCSS("border-top-color", "rgba(0, 0, 0, 0)");
});

test.describe("등록한 여행", () => {
  test.beforeEach(async ({ page }) => { await beforeTheTrip(page); });
  test.beforeEach(async ({ page, request }) => { await mockServer(request).reset(); await useKorean(page); await agree(page); });

  test("일정 칸은 가운데 상자에 회색 테두리 · 채팅 칸에 들어가면 입력 막대가 바닥에 폭 가득 붙고, 일정으로 돌아오면 다시 뜬다", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await registerStubTrip(page);
    await expect(focused(page)).toHaveCount(1);
    await expect(focused(page)).toHaveCSS("border-top-color", await strong(page));
    await openPane(page, "채팅");
    const bar = page.locator("div[class*=chatBar][data-open]");
    await expect(bar).toHaveAttribute("data-docked");
    const box = await bar.evaluate((element) => { const rect = element.getBoundingClientRect(); return { gap: Math.round(innerHeight - rect.bottom), left: Math.round(rect.left), width: Math.round(rect.width), radius: getComputedStyle(element).borderTopLeftRadius }; });
    expect(box).toEqual({ gap: 0, left: 0, width: 375, radius: "0px" });
    await expect(bar.locator("span[class*=chatField]")).toHaveCSS("border-top-left-radius", "22px");
    await expect(focused(page)).toHaveCount(0);                       // 채팅 칸에서는 일정 목록의 초점을 두지 않는다
    await openPane(page, "일정");
    await expect(page.locator("div[class*=chatBar][data-docked]")).toHaveCount(0);
    await expect(focused(page)).toHaveCount(1);
  });
});
