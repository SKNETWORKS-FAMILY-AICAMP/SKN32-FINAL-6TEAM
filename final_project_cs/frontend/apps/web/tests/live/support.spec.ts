import { expect, test } from "@playwright/test";
import { mockServer, start, noHorizontalScroll } from "./helpers";

test.beforeEach(async ({ page, request }) => {
  await mockServer(request).reset();
  await start(page);
  await page.route("**/v1/web/support/notices", (route) => route.fulfill({ json: { notices: [], maintenance: { enabled: false, message: "" } } }));
});

test("문제 신고 재전송은 같은 요청 번호를 사용하고 기록 완료를 안내한다", async ({ page }) => {
  const drafts: Record<string, unknown>[] = [];
  const inquiry = { id: "inquiry-one", title: "여행 일정 문의", body: "일정 확인 방법을 알려 주세요.", language: "ko", receivedAt: "2026-10-08T01:00:00Z", status: "답변 완료", replies: [{ body: "여행 화면에서 확인할 수 있어요.", operator: "support", at: "2026-10-08T02:00:00Z" }] };
  await page.route("**/v1/web/support/inquiries", async (route) => {
    // Like the server: once recorded (the second send), the list the reopened `/support` asks for has it.
    if (route.request().method() === "GET") return route.fulfill({ json: { inquiries: drafts.length >= 2 ? [inquiry] : [] } });
    drafts.push(route.request().postDataJSON());
    expect(route.request().headers()["x-csrf-token"]).toBeTruthy();
    expect(route.request().headers()["content-type"]).toContain("application/json");
    if (drafts.length === 1) return route.fulfill({ status: 503, json: { error: { code: "temporarily_unavailable", message: "잠시 뒤 다시 시도해 주세요." } } });
    return route.fulfill({ json: { inquiry } });
  });
  // `[2026-10-12]` The list (`/support`) has no form: 「문의 작성」 opens it (`/support/new`), and a recorded inquiry goes back to the list.
  await page.goto("/support");
  await expect(page.getByLabel("제목", { exact: true })).toHaveCount(0);
  await page.getByRole("link", { name: "문의 작성", exact: true }).click();
  await expect(page).toHaveURL(/\/support\/new$/);
  await page.getByLabel("제목", { exact: true }).fill(inquiry.title);
  await page.getByLabel("문의 내용", { exact: true }).fill(inquiry.body);
  await page.getByRole("button", { name: "문의 보내기", exact: true }).click();
  await expect(page.locator("#main-content").getByRole("alert")).toContainText("입력한 내용은 그대로예요");
  await expect(page.getByLabel("문의 내용", { exact: true })).toHaveValue(inquiry.body);
  await page.getByRole("button", { name: "문의 보내기", exact: true }).click();
  await expect(page).toHaveURL(/\/support$/);   // the `sent` mark is taken out of the address once said
  await expect(page.locator("#main-content").getByRole("status")).toContainText("내용을 기록했어요");
  expect(drafts).toHaveLength(2);
  expect(drafts[0].requestId).toBe(drafts[1].requestId);
  // `[2026-10-12]` A row (title · 답변 완료 · date) opens the inquiry's own page: the title and text, and the answer in its own box under them.
  const row = page.locator(`[data-inquiry="${inquiry.id}"]`);
  await expect(row.locator("[data-inquiry-status]")).toHaveText("답변 완료");
  await row.click();
  await expect(page).toHaveURL(new RegExp(`/support/${inquiry.id}$`));
  await expect(page.getByRole("heading", { name: inquiry.title, exact: true })).toBeVisible();
  await expect(page.getByText(inquiry.body, { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "답변" }).getByText(inquiry.replies[0].body, { exact: true })).toBeVisible();
  await page.screenshot({ path: test.info().outputPath("support-previous-reply.png"), fullPage: true });
  await page.setViewportSize({ width: 320, height: 640 });
  await noHorizontalScroll(page);
});

test("공개 공지와 점검 메시지는 화면에 보이고 고객 인증 정보를 보내지 않는다", async ({ page }) => {
  await page.route("**/v1/web/support/notices", async (route) => {
    const headers = await route.request().allHeaders();
    expect(headers.cookie).toBeUndefined();
    expect(headers["x-csrf-token"]).toBeUndefined();
    return route.fulfill({ json: { notices: [{ id: "notice-one", kind: "info", title: "여행 점검 안내", body: "여행 일정은 그대로 보관돼요.", titleEn: "Trip notice", bodyEn: "Your itinerary is kept." }], maintenance: { enabled: true, message: "일정 확인 기능을 점검하고 있어요.", messageEn: "Itinerary checks are under maintenance." } } });
  });
  await page.goto("/mypage");
  const banner = page.getByRole("complementary", { name: "서비스 공지" });
  await expect(banner).toContainText("일정 확인 기능을 점검하고 있어요");
  await expect(banner).toContainText("여행 일정은 그대로 보관돼요");
  await banner.getByRole("button", { name: "공지 닫기", exact: true }).click();
  await expect(banner).toHaveCount(0);
  // `[2026-10-12]` 문의함(옛 「문의하기」) left the my-page card for the menu.
  await expect(page.getByRole("link", { name: "문의하기 · 내 문의와 답변", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "메뉴", exact: true }).click();
  await page.getByRole("dialog", { name: "메뉴" }).getByRole("link", { name: "문의함", exact: true }).click();
  await expect(page).toHaveURL(/\/support$/);
});

test("문의 목록 실패에는 재시도 경로를 제공하고 영어 화면에서 빈 상태를 안내한다", async ({ page }) => {
  let calls = 0;
  await page.addInitScript(() => localStorage.setItem("tripilot.web.settings.v1", JSON.stringify({ language: "en" })));
  await page.route("**/v1/web/support/inquiries", async (route) => {
    calls += 1;
    return calls === 1 ? route.fulfill({ status: 503, json: { error: { code: "busy", message: "Unavailable" } } }) : route.fulfill({ json: { inquiries: [] } });
  });
  await page.goto("/support");
  await expect(page.locator("#main-content").getByRole("alert")).toContainText("Could not load the list");
  await page.getByRole("button", { name: "Refresh records", exact: true }).click();
  await expect(page.getByText("No inquiries yet. Use Write an inquiry above to send your first one.")).toBeVisible();
});
// `[2026-10-12 사용자 지시]` 「내 문의」는 높이를 고정한 흰 칸: 비면 안내 한 줄(가운데), 있으면 한 줄짜리 다섯 개씩 — 최근 문의(접수 시각)가 위,
// 줄마다 문의 중 · 답변 완료와 날짜. 페이지 단추는 늘 있다.
test("내 문의는 최근 문의가 위에 오는 고정 높이 흰 칸에 다섯 줄씩(문의 중 · 답변 완료) 보이고, 비어도 칸 높이와 페이지 단추는 그대로다", async ({ page }) => {
  // index 0 = the newest. The server orders by the last change, so the answered one (index 5, answered today) comes first from it.
  const make = (index: number) => ({ id: `inquiry-${index + 1}`, title: `여행 문의 ${index + 1}`, body: "일정 확인을 도와 주세요.", language: "ko",
    receivedAt: `2026-10-${String(12 - index).padStart(2, "0")}T03:00:00Z`, status: index === 5 ? "답변 완료" : index === 1 ? "처리 중" : "접수",
    replies: index === 5 ? [{ body: "확인했어요.", operator: "ops", at: "2026-10-12T06:00:00Z" }] : [] });
  const newest = Array.from({ length: 7 }, (_, index) => make(index));
  let served = [newest[5], ...newest.filter((_, index) => index !== 5)];
  await page.route("**/v1/web/support/inquiries", (route) => route.fulfill({ json: { inquiries: served } }));
  await page.goto("/support");
  await expect(page.getByRole("heading", { name: "문의함", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "내 문의", exact: true })).toBeVisible();
  const titles = page.locator("#main-content [data-inquiry-title]");
  const states = page.locator("#main-content [data-inquiry-status]");
  await expect(titles).toHaveText(newest.slice(0, 5).map((item) => item.title));
  await expect(states).toHaveText(["문의 중", "문의 중", "문의 중", "문의 중", "문의 중"]);   // 접수 · 처리 중 → 문의 중
  const box = page.locator("[data-inquiry-box]");
  const height = (await box.boundingBox())!.height;
  const pages = page.getByRole("navigation", { name: "내 문의 페이지 이동" });
  await expect(pages.getByRole("button", { name: "이전 페이지" })).toBeDisabled();
  await expect(pages.getByRole("button", { name: "1페이지" })).toHaveAttribute("aria-current", "page");
  await pages.getByRole("button", { name: "2페이지" }).click();
  await expect(titles).toHaveText(newest.slice(5).map((item) => item.title));
  await expect(states).toHaveText(["답변 완료", "문의 중"]);
  expect((await box.boundingBox())!.height).toBe(height);
  await expect(pages.getByRole("button", { name: "다음 페이지" })).toBeDisabled();
  await noHorizontalScroll(page);
  served = [];
  await page.getByRole("button", { name: "접수 기록 새로고침", exact: true }).click();
  await expect(page.getByText("아직 접수한 문의가 없어요. 위의 「문의 작성」으로 첫 문의를 보내 주세요.", { exact: true })).toBeVisible();
  await expect(titles).toHaveCount(0);
  expect((await box.boundingBox())!.height).toBe(height);
  await expect(pages.getByRole("button", { name: "1페이지" })).toHaveAttribute("aria-current", "page");
  await expect(pages.getByRole("button", { name: "이전 페이지" })).toBeDisabled();
  await expect(pages.getByRole("button", { name: "다음 페이지" })).toBeDisabled();
});

// `[2026-10-12 사용자 지시]` 문의 내역(/support/[id]): 답변이 없으면 답변 칸 없이 기다림 안내, 목록에 없는 번호면 문의함에서 다시 고르라고 말한다.
test("답변이 없는 문의 내역은 문의 중과 기다림 안내만 보이고, 없는 문의 번호는 다시 고르라고 말한다", async ({ page }) => {
  const waiting = { id: "inquiry-wait", title: "등록한 일정이 보이지 않아요", body: "어제 등록한 일정이 목록에 없어요.", language: "ko", receivedAt: "2026-10-12T03:00:00Z", status: "접수", replies: [] };
  await page.route("**/v1/web/support/inquiries", (route) => route.fulfill({ json: { inquiries: [waiting] } }));
  await page.goto(`/support/${waiting.id}`);
  await expect(page.getByRole("heading", { name: waiting.title, exact: true })).toBeVisible();
  await expect(page.getByText(waiting.body, { exact: true })).toBeVisible();
  await expect(page.locator("#main-content [data-inquiry-status]")).toHaveText("문의 중");
  await expect(page.getByRole("region", { name: "답변" })).toHaveCount(0);
  await expect(page.getByText("아직 답변이 없어요. 답변이 달리면 이 아래에 보여요.", { exact: true })).toBeVisible();
  await page.goto("/support/no-such-inquiry");
  await expect(page.locator("#main-content").getByRole("alert")).toContainText("이 문의를 찾을 수 없어요");
  await page.getByRole("link", { name: "문의함", exact: true }).click();
  await expect(page).toHaveURL(/\/support$/);
});
