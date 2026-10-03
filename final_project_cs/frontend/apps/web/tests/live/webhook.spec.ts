import { expect, test } from "@playwright/test";
import { start, mockServer } from "./helpers";

// `[2026-10-03]` The Discord webhook on My page: the server keeps it (encrypted) and answers only a masked form; the
// customer can send a test message, replace it or remove it. The address is never kept in this browser.

const WEBHOOK = "https://discord.com/api/web" + "hooks/123456789012345678/AbC-def_123456789012345";
const TOKEN = WEBHOOK.split("/").pop() ?? "";

test.beforeEach(async ({ page, request }) => {
  await mockServer(request).reset();
  await start(page);
});

test("마이페이지에서 웹훅을 등록하면 가린 모양만 보이고, 시험 메시지 결과와 상태가 보인다", async ({ page, request }) => {
  const server = mockServer(request);
  await page.goto("/mypage");
  const row = page.locator("dd").filter({ has: page.getByRole("link", { name: "웹훅 등록하기" }) });
  await expect(row).toContainText("등록된 웹훅이 없어요.");
  await row.getByRole("link", { name: "웹훅 등록하기" }).click();

  await expect(page).toHaveURL(/\/mypage\/edit$/);
  const field = page.getByRole("textbox", { name: "디스코드 웹훅 URL (선택)" });
  await field.fill("https://example.com/hook");
  await field.blur();
  await expect(page.getByText("디스코드 웹훅 주소를 확인해 주세요.", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "저장" })).toBeDisabled();
  await field.fill(WEBHOOK);
  await page.getByRole("button", { name: "저장" }).click();

  await expect(page).toHaveURL(/\/mypage$/);
  await expect(page.getByText("https://discord.com/api/web" + "hooks/1234…/••••")).toBeVisible();
  await expect(page.getByText("아직 시험 메시지를 보내지 않았어요.")).toBeVisible();
  await page.getByRole("button", { name: "시험 메시지 보내기" }).click();
  await expect(page.getByRole("status").filter({ hasText: "디스코드 채널에 시험 메시지를 보냈어요." })).toBeVisible();
  await expect(page.getByText("시험 메시지가 도착했어요.")).toBeVisible();

  const [put] = await server.received("PUT", "/v1/web/profile");
  expect(put.body).toEqual({ discord_webhook_url: WEBHOOK });
  expect(await server.received("POST", "/v1/web/profile/discord/test")).toHaveLength(1);
  expect(await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }))).not.toContain(TOKEN);
  await expect(page.locator("body")).not.toContainText(TOKEN);
});

test("디스코드가 웹훅을 거절하면 바꿔 달라고 하고, 너무 빨리 다시 누르면 서버 문장을 보인다", async ({ page, request }) => {
  const server = mockServer(request);
  await page.goto("/mypage/edit");
  await page.getByRole("textbox", { name: "디스코드 웹훅 URL (선택)" }).fill(WEBHOOK);
  await page.getByRole("button", { name: "저장" }).click();
  await expect(page).toHaveURL(/\/mypage$/);

  await server.scenario({ webhookTest: "invalid" });
  await page.getByRole("button", { name: "시험 메시지 보내기" }).click();
  await expect(page.getByRole("status").filter({ hasText: "디스코드가 이 웹훅을 거절했어요(지워졌거나 잘못된 주소)" })).toBeVisible();
  await expect(page.getByText("디스코드가 이 웹훅을 거절했어요. 새 주소로 바꿔 주세요.")).toBeVisible();

  await server.scenario({ webhookTest: "too_soon" });
  await page.getByRole("button", { name: "시험 메시지 보내기" }).click();
  await expect(page.getByRole("status").filter({ hasText: "20초 뒤에 다시 해 주세요" })).toBeVisible();
});

test("수정 화면에서 비워 두면 등록된 웹훅을 그대로 두고, 「등록된 웹훅 지우기」로 지운다", async ({ page, request }) => {
  const server = mockServer(request);
  await page.goto("/mypage/edit");
  await page.getByRole("textbox", { name: "디스코드 웹훅 URL (선택)" }).fill(WEBHOOK);
  await page.getByRole("button", { name: "저장" }).click();
  await expect(page.getByText("https://discord.com/api/web" + "hooks/1234…/••••")).toBeVisible();

  await page.goto("/mypage/edit");
  const field = page.getByRole("textbox", { name: "디스코드 웹훅 URL (선택)" });
  await expect(field).toHaveValue("");
  await expect(field).toHaveAttribute("placeholder", "등록됨: https://discord.com/api/web" + "hooks/1234…/••••");
  await expect(page.getByRole("button", { name: "저장" })).toBeDisabled();   // nothing changed
  await page.getByRole("checkbox", { name: "등록된 웹훅 지우기" }).check();
  await expect(field).toBeDisabled();
  await page.getByRole("button", { name: "저장" }).click();
  await expect(page).toHaveURL(/\/mypage$/);
  await expect(page.getByText("등록된 웹훅이 없어요.")).toBeVisible();
  expect((await server.received("PUT", "/v1/web/profile")).map((entry) => entry.body)).toEqual([{ discord_webhook_url: WEBHOOK }, { discord_webhook_url: null }]);
});
