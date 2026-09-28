import { expect, test } from "@playwright/test";
import { KEY_STORAGE, start, stub, TRIP_ID } from "./helpers";

test.beforeEach(async ({ request }) => { await stub(request).reset(); });

test("내 여행이 있으면 첫 화면의 「내 여행」 카드에 뜨고 그 여행으로 간다", async ({ page }) => {
  await start(page);
  await page.goto("/");
  const card = page.getByRole("region", { name: "내 여행", exact: true });
  await expect(card).toBeVisible();
  await expect(card).toContainText("내 여행");
  await card.getByRole("link").click();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));
});

test("실제 연결의 내 여행 목록은 삭제를 흉내 내지 않는다: 선택 삭제·휴지통이 꺼져 있고 이유를 알리며, 서버에 삭제를 요청하지 않는다", async ({ page, request }) => {
  const server = stub(request);
  await start(page);
  await page.goto("/trips");
  const row = page.locator("#main-content li");
  await expect(row).toHaveCount(1);
  await expect(page.getByText("실제 연결에서 여행 삭제는 아직 지원하지 않아요.")).toBeVisible();
  await expect(page.getByRole("button", { name: "선택 삭제" })).toBeDisabled();
  await expect(row.getByRole("button", { name: /삭제$/ })).toBeDisabled();
  await row.getByRole("link").click();
  await expect(page).toHaveURL(new RegExp(`/trips/${TRIP_ID}$`));
  expect((await server.log()).filter((entry) => entry.method === "DELETE")).toHaveLength(0);
});

test("여행이 없으면 「아직 등록한 여행이 없어요」가 뜨고, 키가 없으면 목록을 묻느라 새 사용자를 만들지도 않는다", async ({ page, request }) => {
  const server = stub(request);
  await server.scenario({ trips: "none" });
  await start(page);
  await page.goto("/");
  await expect(page.getByRole("region", { name: "내 여행", exact: true })).toContainText("아직 등록한 여행이 없어요.");

  await server.reset();
  const fresh = await page.context().browser()!.newContext();
  const first = await fresh.newPage();
  await first.goto("http://127.0.0.1:3102/");
  await expect(first.getByRole("region", { name: /내 여행|My trips/, exact: false }).first()).toBeVisible();
  const issued = (await server.log()).filter((entry) => entry.path.endsWith("/v1/web/session"));
  expect(issued).toHaveLength(0);
  await fresh.close();
});

test("메뉴에서 다른 기기의 키를 넣으면: 틀린 키는 서버 문장으로 거절되고 저장된 키는 그대로, 아는 키는 바뀐다", async ({ page, request }) => {
  const server = stub(request);
  await start(page, null);                      // 이 기기에는 키가 없다
  await page.goto("/start");
  await page.getByRole("button", { name: "메뉴" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("내 사용자 키")).toBeVisible();
  await expect(dialog.getByRole("button", { name: /다시 발급받기/ })).toHaveCount(0);   // 키가 없으면 재발급 단추도 없다

  await dialog.getByLabel("이미 가진 키로 열기").fill("acop_u_wrong");
  await dialog.getByRole("button", { name: "이 키로 열기" }).click();
  await expect(dialog.getByRole("alert")).toHaveText("사용자 키가 없거나 맞지 않는다");
  expect(await page.evaluate((key) => localStorage.getItem(key), KEY_STORAGE)).toBeNull();

  await dialog.getByLabel("이미 가진 키로 열기").fill("  acop_u_known  ");
  await dialog.getByRole("button", { name: "이 키로 열기" }).click();
  await expect(dialog.getByRole("status")).toContainText("이 키로 바꿨어요");
  expect(await page.evaluate((key) => localStorage.getItem(key), KEY_STORAGE)).toBe("acop_u_known");
  const checks = await server.received("GET", "/v1/web/trips");
  // 틀린 키 → 아는 키 순서로 서버에 물었고, 그 뒤 목록을 다시 읽는다면 모두 새 키로
  const askedWith = checks.map((entry) => entry.key);
  expect(askedWith.slice(0, 2)).toEqual(["acop_u_wrong", "acop_u_known"]);
  expect(askedWith.slice(2).every((key) => key === "acop_u_known")).toBe(true);
});

test("키 재발급: 확인 단계를 거치고, 취소하면 아무것도 안 바뀌며, 하면 새 키가 저장되고 한 번 보인다", async ({ page, request }) => {
  const server = stub(request);
  await start(page);
  await page.goto("/start");
  await page.getByRole("button", { name: "메뉴" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: /다시 발급받기/ }).click();
  await expect(dialog).toContainText("옛 키는 바로 쓸 수 없게 돼요");
  await dialog.getByRole("button", { name: "취소" }).click();
  await expect(dialog.getByRole("button", { name: /다시 발급받기/ })).toBeVisible();
  expect(await server.received("POST", "/rotate")).toHaveLength(0);
  expect(await page.evaluate((key) => localStorage.getItem(key), KEY_STORAGE)).toBe("acop_u_known");

  await dialog.getByRole("button", { name: /다시 발급받기/ }).click();
  await dialog.getByRole("button", { name: "키 다시 발급" }).click();
  await expect(dialog.getByRole("status").filter({ hasText: "새 키를 받았어요" })).toBeVisible();
  // 메뉴를 연 그 자리에서 새 키가 바로 보인다(첫 화면·온보딩 틀에는 화면 위 안내가 없다)
  const inMenu = dialog.getByRole("status").filter({ hasText: "내 여행 열쇠를 따로 보관해 주세요" });
  await expect(inMenu.getByRole("textbox")).toHaveValue(/^acop_u_rotated_/);
  const rotated = await page.evaluate((key) => localStorage.getItem(key), KEY_STORAGE);
  expect(rotated).toMatch(/^acop_u_rotated_/);
  expect((await server.received("POST", "/rotate"))[0].key).toBe("acop_u_known");   // 옛 키로 요청했다

  // 여행 화면에서 새 키가 한 번 보인다. 그 사이 옛 키는 서버에서 무효다.
  await page.goto(`/trips/${TRIP_ID}`);
  const notice = page.getByRole("status").filter({ hasText: "내 여행 열쇠를 따로 보관해 주세요" });
  await expect(notice).toContainText("새 키예요. 옛 키는 더 이상 쓸 수 없어요");
  await expect(notice.getByRole("textbox")).toHaveValue(rotated!);
  await notice.getByRole("button", { name: "따로 보관했어요" }).click();
  await expect(notice).toHaveCount(0);
});

test("키가 거절되면(서버가 모르는 키) 조용히 새 사용자가 되지 않고 알린다", async ({ page }) => {
  await start(page, "acop_u_expired");
  await page.goto(`/trips/${TRIP_ID}`);
  await expect(page.getByText(/저장된 사용자 키가 더 이상 맞지 않아요/)).toBeVisible();
  expect(await page.evaluate((key) => localStorage.getItem(key), KEY_STORAGE)).toBeNull();
});

test("내 여행 목록을 읽지 못해도(서버 500) 첫 화면은 그대로 쓸 수 있고, 못 읽었다고 알린다(여행이 없다는 말이 아니다)", async ({ page, request }) => {
  await stub(request).scenario({ fail: "trips" });
  await start(page);
  await page.goto("/");
  const card = page.getByRole("region", { name: "내 여행", exact: true });
  await expect(card.getByRole("alert")).toBeVisible();
  await expect(card.getByRole("button", { name: "다시 불러오기" })).toBeVisible();
  await expect(card).not.toContainText("아직 등록한 여행이 없어요");
});
