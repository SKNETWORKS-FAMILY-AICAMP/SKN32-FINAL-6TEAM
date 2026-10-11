import { expect, test } from "@playwright/test";
import { agree, APP, checkPlan, mockServer, openRegistration, SESSION_COOKIE, start, STUB } from "./helpers";

test.beforeEach(async ({ page, request }) => {
  await mockServer(request).reset();
  await start(page);
  await agree(page);
});

test("게스트는 한 소셜 버튼으로 로그인하고 원래 작성 화면과 글을 이어간다", async ({ page, request }) => {
  await openRegistration(page);
  const text = "서울 여행\n09:00 경복궁\n12:00 광장시장";
  await page.getByLabel("나의 여행 계획").fill(text);
  await page.goto("/mypage?returnTo=%2Ftrips%2Fnew#accounts");
  const group = page.getByRole("group", { name: "소셜 계정" });
  await expect(group.getByRole("button", { name: "Google 계정으로 계속", exact: true })).toHaveCount(1);
  await expect(group).not.toContainText("게스트 여행은 사라지고");
  await group.getByRole("button", { name: "Google 계정으로 계속", exact: true }).click();
  await expect(page.getByRole("heading", { name: "구글 계정으로 로그인했어요" })).toBeVisible();
  const [started] = await mockServer(request).received("POST", "/google/start");
  expect(started.body).toMatchObject({ mode: "login" });
  expect(started.csrf).toBe("csrf-known");
  expect((await page.context().cookies(STUB)).find((cookie) => cookie.name === SESSION_COOKIE)?.value).toMatch(/^member-session-/);
  await page.getByRole("link", { name: "계속하기", exact: true }).click();
  await expect(page).toHaveURL(/\/trips\/new$/);
  await expect(page.getByLabel("나의 여행 계획")).toHaveValue(text);
});

test("게스트 한도로 거절된 첨부 파일과 글은 소셜 화면 왕복 뒤 함께 복구된다", async ({ page }) => {
  await page.route("**/v1/web/trip-intakes", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    await route.fulfill({ status: 403, contentType: "application/json", headers: { "Access-Control-Allow-Origin": APP, "Access-Control-Allow-Credentials": "true" },
      body: JSON.stringify({ error: { code: "guest_trip_limit", message: "로그인하면 여행을 더 추가할 수 있어요", login_required: true } }) });
  });
  await openRegistration(page);
  const text = "로그인 뒤 이어갈 서울 여행";
  await page.getByLabel("나의 여행 계획").fill(text);
  await page.locator("#plan-files").setInputFiles({ name: "seoul-schedule.txt", mimeType: "text/plain", buffer: Buffer.from("09:00 경복궁") });
  await checkPlan(page);
  await page.getByRole("button", { name: "계정으로 계속하기", exact: true }).click();
  await expect(page).toHaveURL(/\/mypage\?returnTo=/);
  await page.getByRole("group", { name: "소셜 계정" }).getByRole("button", { name: "Google 계정으로 계속", exact: true }).click();
  await expect(page.getByRole("heading", { name: "구글 계정으로 로그인했어요" })).toBeVisible();
  await page.getByRole("link", { name: "계속하기", exact: true }).click();
  await expect(page.getByLabel("나의 여행 계획")).toHaveValue(text);
  await expect(page.getByText("seoul-schedule.txt", { exact: true })).toBeVisible();
  await expect(page.locator('[data-pane="files"]')).toHaveAttribute("data-active", "true");
});
