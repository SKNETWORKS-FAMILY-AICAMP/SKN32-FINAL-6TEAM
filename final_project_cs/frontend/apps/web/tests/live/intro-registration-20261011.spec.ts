import { expect, test, type Page } from "@playwright/test";
import { agree, mockServer, noHorizontalScroll, start } from "./helpers";

async function watchLoading(page: Page) {
  await page.evaluate(() => {
    const seen: string[] = [];
    Object.assign(window, { registrationLoadingSeen: seen });
    new MutationObserver((records) => {
      for (const record of records) for (const node of record.addedNodes) {
        const text = node.textContent ?? "";
        if (text.includes("여행 정보를 불러오고 있어요")) seen.push(text);
      }
    }).observe(document.body, { childList: true, subtree: true });
  });
}

for (const width of [375, 1280]) {
  test.describe(`${width}px 시작 화면`, () => {
    test.use({ viewport: { width, height: 812 } });
    test.beforeEach(async ({ page, request }) => {
      await mockServer(request).reset();
      await start(page);
    });

    test("홈 버튼으로 입력 화면을 열 때 로컬 초안 때문에 로딩 화면이 끼어들지 않는다", async ({ page, request }) => {
      await page.goto("/");
      const cta = page.getByRole("button", { name: "내 일정 시작하기" });
      await cta.scrollIntoViewIfNeeded();
      await expect(page.getByText("약관에 동의했어요.", { exact: false })).toBeVisible();   // `[2026-10-16 ST4F-601]` 동의한 사람의 안내 문구
      // `[2026-10-22 ST4F-715]` 홈 `/` 은 공개 화면이라 동의 관문이 서버 동의를 다시 읽지 않는다(`consent-gate.tsx`) — 그 요청은 기다리지 않는다
      await watchLoading(page);
      await cta.click();
      await expect(page).toHaveURL(/\/trips\/new$/);
      await expect(page.getByLabel("나의 여행 계획")).toBeVisible();
      expect(await page.evaluate(() => (window as unknown as { registrationLoadingSeen: string[] }).registrationLoadingSeen)).toEqual([]);
      expect((await mockServer(request).received("POST", "/v1/web/trip-intakes")).length).toBe(0);
      await noHorizontalScroll(page);
      if (process.env.INTRO_SHOTS) await page.screenshot({ path: `${process.env.INTRO_SHOTS}/registration-${width}.png`, fullPage: true });
    });

    test("응답이 없는 cs 프로젝트 API와 무관하게 초안을 복원하고 다시 입력할 수 있다", async ({ page }) => {
      await page.goto("/");
      await page.evaluate(() => sessionStorage.setItem("tripilot.web.registration-draft.v1", "10/15 09:00 경복궁 관람"));
      await page.route("**/v1/web/**", async (route) => { await route.abort("internetdisconnected"); });
      await page.goto("/trips/new");
      const input = page.getByLabel("나의 여행 계획");
      await expect(input).toHaveValue("10/15 09:00 경복궁 관람");
      await input.fill("10/15 10:00 광장시장");
      await page.reload();
      await expect(input).toHaveValue("10/15 10:00 광장시장");
    });

    test("브라우저 임시 저장을 쓸 수 없어도 입력 화면을 표시하고 저장 불가를 알린다", async ({ page }) => {
      await agree(page);
      await page.addInitScript(() => {
        const get = Storage.prototype.getItem, set = Storage.prototype.setItem;
        Storage.prototype.getItem = function (key) {
          if (key === "tripilot.web.registration-draft.v1") throw new DOMException("blocked", "SecurityError");
          return get.call(this, key);
        };
        Storage.prototype.setItem = function (key, value) {
          if (key === "tripilot.web.registration-draft.v1") throw new DOMException("blocked", "SecurityError");
          return set.call(this, key, value);
        };
      });
      await page.goto("/trips/new");
      const input = page.getByLabel("나의 여행 계획");
      await expect(input).toBeVisible();
      await input.fill("10/15 09:00 경복궁");
      await expect(input).toHaveValue("10/15 09:00 경복궁");
      await expect(page.getByText("임시 저장을 사용할 수 없어요.", { exact: false })).toBeVisible();
    });
  });
}
