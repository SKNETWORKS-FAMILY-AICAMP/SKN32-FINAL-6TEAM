import { expect, test } from "@playwright/test";
import { mockServer, start, noHorizontalScroll } from "./helpers";

test.beforeEach(async ({ page, request }) => {
  await mockServer(request).reset();
  await start(page);
  await page.route("**/v1/web/support/notices", (route) => route.fulfill({ json: { notices: [], maintenance: { enabled: false, message: "" } } }));
});

test("문의 재전송은 같은 요청 번호를 사용하고 답변을 고객 화면에 표시한다", async ({ page }) => {
  const drafts: Record<string, unknown>[] = [];
  const inquiry = { id: "inquiry-one", title: "여행 일정 문의", body: "일정 확인 방법을 알려 주세요.", language: "ko", receivedAt: "2026-10-08T01:00:00Z", status: "답변 완료", replies: [{ body: "여행 화면에서 확인할 수 있어요.", operator: "support", at: "2026-10-08T02:00:00Z" }] };
  await page.route("**/v1/web/support/inquiries", async (route) => {
    if (route.request().method() === "GET") return route.fulfill({ json: { inquiries: [] } });
    drafts.push(route.request().postDataJSON());
    expect(route.request().headers()["x-csrf-token"]).toBeTruthy();
    expect(route.request().headers()["content-type"]).toContain("application/json");
    if (drafts.length === 1) return route.fulfill({ status: 503, json: { error: { code: "temporarily_unavailable", message: "잠시 뒤 다시 시도해 주세요." } } });
    return route.fulfill({ json: { inquiry } });
  });
  await page.goto("/support");
  await page.getByLabel("제목", { exact: true }).fill(inquiry.title);
  await page.getByLabel("문의 내용", { exact: true }).fill(inquiry.body);
  await page.getByRole("button", { name: "문의 보내기", exact: true }).click();
  await expect(page.locator("#main-content").getByRole("alert")).toContainText("입력한 내용은 그대로예요");
  await expect(page.getByLabel("문의 내용", { exact: true })).toHaveValue(inquiry.body);
  await page.getByRole("button", { name: "문의 보내기", exact: true }).click();
  await expect(page.locator("#main-content").getByRole("status")).toContainText("문의를 접수했어요");
  expect(drafts).toHaveLength(2);
  expect(drafts[0].requestId).toBe(drafts[1].requestId);
  await page.getByText(`${inquiry.title} · 답변 완료`, { exact: true }).click();
  await expect(page.getByText(inquiry.replies[0].body, { exact: true })).toBeVisible();
  await expect(page.getByLabel("제목", { exact: true })).toHaveValue("");
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
  await page.getByRole("link", { name: "문의하기 · 내 문의와 답변", exact: true }).click();
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
  await page.getByRole("button", { name: "Refresh replies", exact: true }).click();
  await expect(page.getByText("No inquiries yet. Send your first inquiry above.")).toBeVisible();
});
