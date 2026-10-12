import { test, type Page } from "@playwright/test";
import { head } from "./plan-check-kit";
import { mockServer, start } from "./helpers";

// 화면 촬영은 시험 결과 폴더에만 기록한다.
const INTAKE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const OUT = process.env.SHOT_DIR ?? "test-results/shots-plan";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });
test.use({ viewport: { width: 402, height: 874 } });

const shot = (page: Page, name: string) => page.screenshot({ path: `${OUT}/${name}.png` });

test("촬영: 읽는 중 → 확인 재생 → 결과", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ review: "on", board: "rich", intakeEvents: "on", readingPolls: 1, intakeRoutes: "on" });
  await start(page);
  await page.goto(`/intakes/${INTAKE}`, { waitUntil: "commit" });
  for (let at = 0; at < 14; at += 1) {
    await page.waitForTimeout(450);
    await shot(page, `0${String(at).padStart(2, "0")}_flow`);
  }
});

test("촬영: 결과 화면의 여러 모습", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ review: "on", board: "rich", readingPolls: 0, intakeRoutes: "on" });
  await start(page);
  await page.goto(`/intakes/${INTAKE}`);
  await page.getByRole("region", { name: /계획 확인/ }).waitFor();
  await page.waitForTimeout(2500);
  await shot(page, "10_done");
  await head(page, "경복궁 관람").click();
  await page.waitForTimeout(500);
  await shot(page, "11_open_card");
  await head(page, "경복궁 관람").click();
  await page.waitForTimeout(400);
  await shot(page, "12_card_toggled_off");
  await page.getByRole("button", { name: /경복궁 관람 시간 고치기/ }).click();
  await page.waitForTimeout(400);
  await shot(page, "13_time_edit");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "올리브영 삭제" }).click();
  await page.waitForTimeout(500);
  await shot(page, "14_marked_removed");
  await page.getByRole("button", { name: /올리브영 삭제 되돌리기/ }).click();
  await page.getByRole("button", { name: "전체 자동 추천" }).click();
  await page.waitForTimeout(2200);
  await shot(page, "15_preview_after");
  await page.locator("section[aria-labelledby='plan-check-sheet-title'] > div").nth(0).evaluate((el) => el.scrollTo({ top: 0 }));
  await page.waitForTimeout(700);
  await shot(page, "16_preview_before");
  await page.getByRole("button", { name: "목록 높이 바꾸기" }).click();
  await page.waitForTimeout(500);
  await page.getByRole("button", { name: "목록 높이 바꾸기" }).click();
  await page.waitForTimeout(700);
  await shot(page, "17_peek_compact");
});
