import { expect, test } from "@playwright/test";
import { mockServer, start, TRIP_ID } from "./helpers";
import { INTAKE, needsBadge } from "./plan-check-kit";
import { useMapTiles } from "./capture-map-tiles";

// 현재 app의 13개 진입 경로. 폐기 주소의 이동과 전송 중 주소 재방문도 포함한다.
const screens = [
  { name: "intro", path: "/" },
  { name: "terms-preferences", path: "/start" },
  { name: "registration", path: "/trips/new" },
  { name: "trips", path: "/trips" },
  { name: "registered-trip", path: `/trips/${TRIP_ID}`, map: true },
  { name: "verification-redirect", path: `/trips/${TRIP_ID}/verification`, map: true, final: `/trips/${TRIP_ID}` },
  { name: "results-redirect", path: `/trips/${TRIP_ID}/results`, map: true, final: `/trips/${TRIP_ID}` },
  { name: "intake", path: `/intakes/${INTAKE}`, map: true, intake: true },
  { name: "starting-revisit", path: "/intakes/starting", final: "/trips/new" },
  { name: "account", path: "/mypage" },
  { name: "profile", path: "/mypage/edit" },
  { name: "support", path: "/support" },
  { name: "social-cancelled", path: "/auth/done?error=cancelled" },
];

for (const width of [375, 1280]) {
  for (const screen of screens) {
    test(`전체 경로 · ${screen.name} · ${width}px: 화면 표시·가로 넘침·실행 오류`, async ({ page, request }, testInfo) => {
      await page.setViewportSize({ width, height: 900 });
      await mockServer(request).reset();
      await mockServer(request).scenario({ trips: "one", review: "on", board: "rich", readingPolls: 0 });
      await start(page);
      const errors: string[] = [];
      page.on("pageerror", error => errors.push(error.message));
      const tilesReady = screen.map ? await useMapTiles(page) : null;
      const response = await page.goto(screen.path);
      expect(response?.status()).toBeLessThan(400);
      await expect(page.locator("#main-content")).toBeVisible();
      if (screen.final) await expect(page).toHaveURL(new RegExp(`${screen.final}$`));
      if (screen.intake) await expect(needsBadge(page)).toBeVisible();
      if (screen.name === "registration" || screen.name === "starting-revisit") {
        await expect(page.locator("#test-plan-code")).toHaveAttribute("aria-disabled", "false");
        await expect(page.locator("button[data-plan-code]")).toHaveCount(15);
      }
      if (screen.name === "support") {
        await expect(page.getByText("아직 접수한 문의가 없어요. 위에서 첫 문의를 보내 주세요.", { exact: true })).toBeVisible();
        await expect(page.locator("#main-content").getByRole("alert")).toHaveCount(0);
      }
      if (tilesReady) await tilesReady();
      await page.evaluate(() => document.fonts.ready);
      await page.waitForTimeout(400);
      const dimensions = await page.evaluate(() => {
        const main = document.querySelector<HTMLElement>("#main-content")!;
        const frame = main.closest<HTMLElement>('div[data-journey="true"]');
        const scroll = frame?.querySelector<HTMLElement>(':scope > [class*="scroll"]');
        return { document: document.documentElement.scrollWidth - innerWidth, main: main.scrollWidth - main.clientWidth, scroll: scroll ? scroll.scrollWidth - scroll.clientWidth : 0, expectsFrameScroll: Boolean(frame), foundFrameScroll: Boolean(scroll) };
      });
      expect(dimensions.foundFrameScroll, "스크롤 기기 틀에서는 실제 스크롤 영역을 검사").toBe(dimensions.expectsFrameScroll);
      expect(dimensions.document, "페이지 전체 가로 넘침").toBeLessThanOrEqual(1);
      expect(dimensions.main, "본문 가로 넘침").toBeLessThanOrEqual(1);
      expect(dimensions.scroll, "기기 틀 가로 넘침").toBeLessThanOrEqual(1);
      expect(errors).toEqual([]);
      await page.screenshot({ path: testInfo.outputPath(`${screen.name}-${width}.png`), fullPage: true });
      await testInfo.attach("route-observation", { body: JSON.stringify({ route: screen.path, landed: page.url(), dimensions, errors }), contentType: "application/json" });
    });
  }
}
