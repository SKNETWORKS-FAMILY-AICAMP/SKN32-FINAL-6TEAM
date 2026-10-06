import { expect, test, type Page } from "@playwright/test";
import { mockServer, start, TRIP_ID } from "./helpers";

/**
 * `[2026-10-06 사용자 지시 — 설문 화면 구현 인계 3단계]` 등록된 여행의 항로 지킴이 아이콘: 서버가 말한 `guardian` 을 그리고, 누르면 `POST /v1/web/trips/{id}/guardian` 을 부른다(켜 둔 것은 바로 꺼지고 되돌리기 줄,
 * 꺼진 것은 카드로 한 번 묻는다, 서버가 못 받으면 상태 그대로 + 「다시 시도하기」, 알림 링크 `?guardian=on` 은 같은 카드를 바로 연다).
 * 테스트용 mock 서버로 도는 자동 시험이다(화면 반응을 본다 — 실서버 확인 아님).
 */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const icon = (page: Page, name: "항로 지킴이 끄기" | "항로 지킴이 켜기") => page.getByRole("button", { name });
const card = (page: Page) => page.getByRole("dialog");
const saved = (server: ReturnType<typeof mockServer>) => server.received("POST", "/guardian");

async function open(page: Page, request: Parameters<typeof mockServer>[0], guardian: "absent" | "on" | "off", extra: Record<string, unknown> = {}, query = "") {
  const server = mockServer(request);
  await server.scenario({ guardian, ...extra });
  await start(page);
  await page.goto(`/trips/${TRIP_ID}${query}`);
  await expect(page.getByRole("heading", { name: "나의 여행", exact: true })).toBeVisible();
  return server;
}

test("서버가 guardian 을 말하지 않으면(옛 서버) 아이콘을 그리지 않는다", async ({ page, request }) => {
  await open(page, request, "absent");
  await page.waitForTimeout(500);
  await expect(page.getByRole("button", { name: /항로 지킴이/ })).toHaveCount(0);
});

test("켜져 있으면 「끄기」 아이콘이 보이고, 누르면 바로 꺼지며 되돌리기 줄은 저절로 사라지지 않고, 되돌리면 다시 켜진다(서버에는 header 로 기록)", async ({ page, request }) => {
  const server = await open(page, request, "on");
  await expect(icon(page, "항로 지킴이 끄기")).toContainText("지금 켜져 있어요");
  await icon(page, "항로 지킴이 끄기").click();
  await expect(icon(page, "항로 지킴이 켜기")).toBeVisible();
  const line = page.getByRole("status").filter({ hasText: "항로 지킴이를 껐어요. 문제가 생기면 물어볼게요." });
  await expect(line).toBeVisible();
  // 알림줄은 머리줄 아래에 서서 아이콘을 가리지 않는다
  const iconBox = (await icon(page, "항로 지킴이 켜기").boundingBox())!;
  const lineBox = (await line.locator("xpath=ancestor::div[1]").boundingBox())!;
  expect(lineBox.y).toBeGreaterThanOrEqual(iconBox.y + iconBox.height);
  expect((await saved(server)).map((entry) => entry.body)).toEqual([{ enabled: false, via: "header" }]);
  await page.waitForTimeout(5500);
  await expect(line).toBeVisible();
  await line.getByRole("button", { name: "되돌리기" }).click();
  await expect(icon(page, "항로 지킴이 끄기")).toBeVisible();
  await expect(line).toHaveCount(0);
  expect((await saved(server)).map((entry) => entry.body)).toEqual([{ enabled: false, via: "header" }, { enabled: true, via: "header" }]);
  // 서버가 기억한다 — 새로고침해도 같다
  await icon(page, "항로 지킴이 끄기").click();
  await expect(icon(page, "항로 지킴이 켜기")).toBeVisible();
  await page.reload();
  await expect(icon(page, "항로 지킴이 켜기")).toBeVisible();
});

test("꺼져 있으면 누를 때 카드(켜기 / 그대로 두기)가 한 번 묻고, 켜기는 서버에 보내고 「켰어요」 줄을 보이고, 그대로 두기는 아무것도 보내지 않는다", async ({ page, request }) => {
  const server = await open(page, request, "off");
  await icon(page, "항로 지킴이 켜기").click();
  await expect(card(page)).toBeVisible();
  await expect(card(page).getByRole("heading", { name: /항로 지킴이/ })).toBeFocused();
  await expect(card(page)).not.toContainText("끄고 진행하면 문제가 생길 때 먼저 물어봐요.");              // 시작 때의 줄은 없다
  await card(page).getByRole("button", { name: "그대로 두기" }).click();
  await expect(card(page)).toHaveCount(0);
  expect(await saved(server)).toHaveLength(0);
  await expect(icon(page, "항로 지킴이 켜기")).toBeFocused();
  await icon(page, "항로 지킴이 켜기").click();
  await card(page).getByRole("button", { name: "켜기", exact: true }).click();
  await expect(icon(page, "항로 지킴이 끄기")).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "항로 지킴이를 켰어요." })).toBeVisible();
  expect((await saved(server)).map((entry) => entry.body)).toEqual([{ enabled: true, via: "header" }]);
});

test("서버가 못 받으면 상태는 그대로이고 「항로 지킴이를 바꾸지 못했어요」와 「다시 시도하기」가 뜬다. 서버가 돌아오면 다시 시도로 바뀐다", async ({ page, request }) => {
  const server = await open(page, request, "on", { guardianSave: "fail" });
  await icon(page, "항로 지킴이 끄기").click();
  const alert = page.getByRole("alert").filter({ hasText: "항로 지킴이를 바꾸지 못했어요. 연결을 확인하고 다시 시도해 주세요." });
  await expect(alert).toBeVisible();
  await expect(icon(page, "항로 지킴이 끄기")).toBeVisible();                                         // 바뀌지 않았다
  await expect(icon(page, "항로 지킴이 켜기")).toHaveCount(0);
  await server.scenario({ guardianSave: "ok" });
  await alert.getByRole("button", { name: "다시 시도하기" }).click();
  await expect(icon(page, "항로 지킴이 켜기")).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "항로 지킴이를 껐어요." })).toBeVisible();
  await expect(alert).toHaveCount(0);
});

test("알림 링크(?guardian=on): 꺼져 있으면 카드가 바로 열리고, 켜기는 notice 로 기록하며 주소의 표시가 사라진다. 링크만으로는 아무것도 켜지지 않는다", async ({ page, request }) => {
  const server = await open(page, request, "off", {}, "?guardian=on");
  await expect(card(page)).toBeVisible();
  expect(await saved(server)).toHaveLength(0);                                                         // 열렸을 뿐 켜지지 않았다
  await card(page).getByRole("button", { name: "켜기", exact: true }).click();
  await expect(icon(page, "항로 지킴이 끄기")).toBeVisible();
  expect((await saved(server)).map((entry) => entry.body)).toEqual([{ enabled: true, via: "notice" }]);
  await expect(page).not.toHaveURL(/guardian=on/);
});

test("알림 링크로 열었다가 닫거나 그대로 두면 아무것도 보내지 않고 표시만 지운다. 이미 켜져 있으면 카드를 열지 않는다", async ({ page, request }) => {
  const server = await open(page, request, "off", {}, "?guardian=on");
  await expect(card(page)).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(card(page)).toHaveCount(0);
  await expect(page).not.toHaveURL(/guardian=on/);
  expect(await saved(server)).toHaveLength(0);
  await expect(icon(page, "항로 지킴이 켜기")).toBeVisible();

  await server.scenario({ guardian: "on" });
  await page.goto(`/trips/${TRIP_ID}?guardian=on`);
  await expect(icon(page, "항로 지킴이 끄기")).toBeVisible();
  await page.waitForTimeout(500);
  await expect(card(page)).toHaveCount(0);
});

test("영어 화면에서도 아이콘 이름 · 되돌리기 줄이 영어로 나온다", async ({ page, request }) => {
  await page.addInitScript(() => localStorage.setItem("tripilot.web.settings.v1", JSON.stringify({ language: "en", navigation: "fixed" })));
  const server = mockServer(request);
  await server.scenario({ guardian: "on" });
  await start(page);
  await page.goto(`/trips/${TRIP_ID}`);
  await page.getByRole("button", { name: "Turn Course Keeper off" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Course Keeper is off." })).toBeVisible();
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByRole("button", { name: "Turn Course Keeper off" })).toBeVisible();
});
