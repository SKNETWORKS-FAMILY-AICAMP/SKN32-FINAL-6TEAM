import { expect, test } from "@playwright/test";
import { APP, KEY_STORAGE, start, mockServer, TRIP_ID } from "./helpers";

test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

test("내 여행이 있으면 첫 화면의 「내 여행」 카드에 뜨고 그 여행으로 간다", async ({ page }) => {
  await start(page);
  await page.goto("/");
  const card = page.getByRole("region", { name: "내 여행", exact: true });
  await expect(card).toBeVisible();
  await expect(card).toContainText("내 여행");
  await card.getByRole("link").click();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));
});

test("여행이 없으면 「아직 등록한 여행이 없어요」가 뜨고, 키가 없으면 목록을 묻느라 새 사용자를 만들지도 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ trips: "none" });
  await start(page);
  await page.goto("/");
  await expect(page.getByRole("region", { name: "내 여행", exact: true })).toContainText("아직 등록한 여행이 없어요.");

  await server.reset();
  const fresh = await page.context().browser()!.newContext();
  const first = await fresh.newPage();
  await first.goto(`${APP}/`);
  await expect(first.getByRole("region", { name: /내 여행|My trips/, exact: false }).first()).toBeVisible();
  const issued = (await server.log()).filter((entry) => entry.path.endsWith("/v1/web/session"));
  expect(issued).toHaveLength(0);
  await fresh.close();
});

test("마이페이지에서 다른 기기의 토큰을 넣으면: 틀린 토큰은 서버 문장으로 거절되고 저장된 키는 그대로, 아는 토큰은 바뀌고 토큰 칸도 바로 바뀐다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page, null);                      // 이 기기에는 키가 없다
  await page.goto("/mypage");
  const manage = page.getByRole("group", { name: "토큰 관리" });
  await expect(manage).toBeVisible();
  await expect(manage.getByRole("button", { name: /다시 발급받기/ })).toHaveCount(0);   // 키가 없으면 재발급 단추도 없다
  await expect(page.getByText("발급된 토큰이 없어요.")).toBeVisible();

  await manage.getByLabel("다른 기기의 토큰으로 열기").fill("acop_u_wrong");
  await manage.getByRole("button", { name: "이 토큰으로 열기" }).click();
  await expect(manage.getByRole("alert")).toHaveText("사용자 키가 없거나 맞지 않는다");
  expect(await page.evaluate((key) => localStorage.getItem(key), KEY_STORAGE)).toBeNull();

  await manage.getByLabel("다른 기기의 토큰으로 열기").fill("  acop_u_known  ");
  await manage.getByRole("button", { name: "이 토큰으로 열기" }).click();
  await expect(manage.getByRole("status")).toContainText("이 토큰으로 바꿨어요");
  expect(await page.evaluate((key) => localStorage.getItem(key), KEY_STORAGE)).toBe("acop_u_known");
  // 같은 화면의 토큰 칸이 새로고침 없이 새 토큰을 보인다(전에는 다른 탭에서 바뀔 때만 다시 읽었다)
  await expect(page.getByText("발급된 토큰이 없어요.")).toHaveCount(0);
  await page.getByRole("button", { name: "보기", exact: true }).click();
  await expect(page.getByText("acop_u_known", { exact: true })).toBeVisible();
  const askedWith = (await server.received("GET", "/v1/web/trips")).map((entry) => entry.key);
  expect(askedWith.slice(0, 2)).toEqual(["acop_u_wrong", "acop_u_known"]);
  expect(askedWith.slice(2).every((key) => key === "acop_u_known")).toBe(true);
});

test("메뉴에는 토큰 화면이 없고 마이페이지로 가는 길만 있다", async ({ page }) => {
  await start(page);
  await page.goto("/");
  await page.getByRole("button", { name: "메뉴", exact: true }).first().click();
  const dialog = page.getByRole("dialog", { name: "메뉴" });
  await expect(dialog.getByRole("link", { name: /마이페이지/ })).toBeVisible();
  await expect(dialog.getByRole("group", { name: "토큰 관리" })).toHaveCount(0);
  await expect(dialog.getByRole("button", { name: /다시 발급받기/ })).toHaveCount(0);
});

test("토큰 재발급: 확인 단계를 거치고, 취소하면 아무것도 안 바뀌며, 하면 새 토큰이 저장되고 마이페이지 맨 위 안내에 한 번 보인다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page);
  await page.goto("/mypage");
  const manage = page.getByRole("group", { name: "토큰 관리" });
  await manage.getByRole("button", { name: /다시 발급받기/ }).click();
  await expect(manage).toContainText("옛 토큰은 바로 쓸 수 없게 돼요");
  await manage.getByRole("button", { name: "취소" }).click();
  await expect(manage.getByRole("button", { name: /다시 발급받기/ })).toBeVisible();
  expect(await server.received("POST", "/rotate")).toHaveLength(0);
  expect(await page.evaluate((key) => localStorage.getItem(key), KEY_STORAGE)).toBe("acop_u_known");

  await manage.getByRole("button", { name: /다시 발급받기/ }).click();
  await manage.getByRole("button", { name: "토큰 다시 발급" }).click();
  await expect(manage.getByRole("status").filter({ hasText: "새 토큰을 받았어요" })).toBeVisible();
  const rotated = await page.evaluate((key) => localStorage.getItem(key), KEY_STORAGE);
  expect(rotated).toMatch(/^acop_u_rotated_/);
  expect((await server.received("POST", "/rotate"))[0].key).toBe("acop_u_known");   // 옛 키로 요청했다

  // 마이페이지 맨 위에 새 토큰 안내가 한 번 뜬다(안내는 화면에 하나만 — 계획 화면에는 뜨지 않는다)
  const notice = page.getByRole("status").filter({ hasText: "내 여행 열쇠를 따로 보관해 주세요" });
  await expect(notice).toHaveCount(1);
  await expect(notice).toContainText("새 키예요. 옛 키는 더 이상 쓸 수 없어요");
  await expect(notice.getByRole("textbox")).toHaveValue(rotated!);
  await notice.getByRole("button", { name: "따로 보관했어요" }).click();
  await expect(notice).toHaveCount(0);
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(page.getByText("내 여행 열쇠를 따로 보관해 주세요")).toHaveCount(0);
});

test("키가 거절되면(서버가 모르는 키) 조용히 새 사용자가 되지 않고 알린다", async ({ page }) => {
  await start(page, "acop_u_expired");
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(page.getByText(/저장된 사용자 키가 더 이상 맞지 않아요/)).toBeVisible();
  expect(await page.evaluate((key) => localStorage.getItem(key), KEY_STORAGE)).toBeNull();
});

test("내 여행 목록을 읽지 못해도(서버 500) 첫 화면은 그대로 쓸 수 있고, 못 읽었다고 알린다(여행이 없다는 말이 아니다)", async ({ page, request }) => {
  await mockServer(request).scenario({ fail: "trips" });
  await start(page);
  await page.goto("/");
  const card = page.getByRole("region", { name: "내 여행", exact: true });
  await expect(card.getByRole("alert")).toBeVisible();
  await expect(card.getByRole("button", { name: "다시 불러오기" })).toBeVisible();
  await expect(card).not.toContainText("아직 등록한 여행이 없어요");
});
