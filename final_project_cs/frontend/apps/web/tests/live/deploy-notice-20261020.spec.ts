import { expect, test, type Page } from "@playwright/test";
import { mockServer, start } from "./helpers";

/**
 * `[2026-10-20 사용자 지시 · D-CS-019]` 새 판 배포 중 공지 — 서버가 운영자 공지 맨 앞에 붙여 주는 배포 공지(`id` `deploy:…`, 정해 둔 문구)가 상단 공지 띠에 뜨고,
 * 새 판으로 바꾸느라 서버가 답하지 못하는 동안(Caddy 의 503 `service_updating`)에도 **마지막으로 받은 공지가 그대로 남고**, 다시 연결되면 「바뀌었어요」로 바뀐다.
 * mock 서버 시험이다 — 공지 요청은 브라우저 안에서 가로채 답한다(화면 반응). 문구는 서버(`app/application/deploy_notice.py`)가 만드는 그대로 옮겨 적었다.
 */
const DEPLOY = "deploy:09bf0dad12-1792472700";
const notice = (phase: string, kind: string, title: string, body: string, titleEn: string, bodyEn: string) =>
  ({ id: `${DEPLOY}:${phase}`, kind, title, body, titleEn, bodyEn, startsAt: "2026-10-20T14:05", endsAt: null });
const PHASES = {
  preparing: notice("preparing", "점검 예고", "곧 새 판으로 바뀌어요",
    "지금은 그대로 쓰실 수 있어요. 14:05에 시작한 준비가 끝나면 약 2분 동안 연결이 끊길 수 있어요. 저장된 일정은 그대로예요.",
    "A new version is coming shortly", "You can keep using the service for now. When the preparation that started at 14:05 KST finishes, the connection may drop for about 2 min. Your saved plans are safe."),
  switching: notice("switching", "점검 예고", "새 판으로 바꾸는 중이에요",
    "14:11부터 약 2분 동안 연결이 끊길 수 있어요. 저장된 일정은 그대로예요. 화면이 안 열리면 잠시 뒤 다시 시도해 주세요.",
    "Switching to a new version", "From 14:11 KST the connection may drop for about 2 min. Your saved plans are safe. If something does not load, please try again shortly."),
  done: notice("done", "안내", "새 판으로 바뀌었어요", "14:12에 끝났어요. 계속 쓰시면 돼요.", "The new version is live", "Finished at 14:12 KST. You can carry on."),
};
const CADDY_DOWN = { error: { code: "service_updating", message: "서비스를 새 판으로 바꾸는 중이거나 잠시 연결이 끊겼습니다. 잠시 뒤 다시 시도해 주세요." } };

type Mode = keyof typeof PHASES | "down";

async function serveNotices(page: Page) {
  const state = { mode: "preparing" as Mode, calls: 0 };
  await page.route("**/v1/web/support/notices", (route) => {
    state.calls += 1;
    if (state.mode === "down") return route.fulfill({ status: 503, json: CADDY_DOWN, headers: { "Retry-After": "30" } });
    return route.fulfill({ json: { notices: [PHASES[state.mode]], maintenance: { enabled: false, message: "" } } });
  });
  return state;
}

/** The notices are read every 15 s and when the tab comes back — bring the tab back instead of waiting. */
async function readAgain(page: Page, state: { calls: number }) {
  const before = state.calls;
  // React Query listens on the window (`focusManager`); the browser's own event starts at the document and bubbles there.
  await page.evaluate(() => window.dispatchEvent(new Event("visibilitychange")));
  await expect.poll(() => state.calls, { timeout: 10_000 }).toBeGreaterThan(before);
}

const banner = (page: Page) => page.getByRole("complementary", { name: "서비스 공지" });

test.beforeEach(async ({ page, request }) => {
  await mockServer(request).reset();
  await start(page);
});

test("배포 공지가 상단 띠에 뜨고, 바꾸는 동안 서버가 답하지 못해도 남아 있다가, 다시 연결되면 「바뀌었어요」로 바뀐다", async ({ page }) => {
  const state = await serveNotices(page);
  await page.goto("/trips");
  await expect(banner(page).getByRole("heading", { name: "곧 새 판으로 바뀌어요" })).toBeVisible();
  await expect(banner(page).getByText("점검 예고", { exact: true })).toBeVisible();
  await expect(banner(page).getByText(/14:05에 시작한 준비가 끝나면 약 2분 동안/)).toBeVisible();

  state.mode = "switching";
  await readAgain(page, state);
  await expect(banner(page).getByRole("heading", { name: "새 판으로 바꾸는 중이에요" })).toBeVisible();

  // api · web 이 함께 다시 만들어지는 동안 — Caddy 가 503 으로 답한다. 다시 묻기(1초 · 2초 뒤)까지 실패해도 마지막 공지를 그대로 둔다.
  state.mode = "down";
  const before = state.calls;
  await readAgain(page, state);
  await expect.poll(() => state.calls - before, { timeout: 10_000 }).toBeGreaterThanOrEqual(3);
  await expect(banner(page).getByRole("heading", { name: "새 판으로 바꾸는 중이에요" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "서비스 공지를 확인하지 못했어요" })).toHaveCount(0);

  state.mode = "done";
  await readAgain(page, state);
  await expect(banner(page).getByRole("heading", { name: "새 판으로 바뀌었어요" })).toBeVisible();
  await expect(banner(page).getByRole("heading", { name: "새 판으로 바꾸는 중이에요" })).toHaveCount(0);
});

test("앞 단계 공지를 닫아도 다음 단계 공지는 다시 뜬다(단계마다 다른 공지)", async ({ page }) => {
  const state = await serveNotices(page);
  await page.goto("/trips");
  await expect(banner(page).getByRole("heading", { name: "곧 새 판으로 바뀌어요" })).toBeVisible();
  await banner(page).getByRole("button", { name: "공지 닫기" }).click();
  await expect(banner(page)).toHaveCount(0);
  state.mode = "switching";
  await readAgain(page, state);
  await expect(banner(page).getByRole("heading", { name: "새 판으로 바꾸는 중이에요" })).toBeVisible();
});

test("영어 화면은 영어 문구를 보인다(시각은 같은 값 · KST)", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("tripilot.web.settings.v1", JSON.stringify({ language: "en" })));
  await serveNotices(page);
  await page.goto("/trips");
  const english = page.getByRole("complementary", { name: "Service notices" });
  await expect(english.getByRole("heading", { name: "A new version is coming shortly" })).toBeVisible();
  await expect(english.getByText(/started at 14:05 KST finishes, the connection may drop for about 2 min/)).toBeVisible();
});
