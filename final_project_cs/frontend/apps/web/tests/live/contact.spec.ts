import { expect, test } from "@playwright/test";
import { start, mockServer, STUB } from "./helpers";

// 2026-10-01: the recovery email is saved on the server (`PUT /v1/web/profile`) once this browser has a user key, and read
// back when the app opens. These run against the test mock server (not the real one); the real server is checked by hand.
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const email = (page: import("@playwright/test").Page) => page.getByLabel(/토큰 복구용 이메일/);
const save = (page: import("@playwright/test").Page) => page.getByRole("button", { name: "저장", exact: true });
const profileCalls = async (server: ReturnType<typeof mockServer>, method: string) => server.received(method, "/v1/web/profile");

test("마이페이지에서 이메일을 저장하면 서버로 가고, 서버에 있다고 알리며, 새로고침해도 서버 값을 다시 읽는다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page);
  await page.goto("/mypage/edit");
  await email(page).fill("  traveler@example.com ");
  await save(page).click();
  await expect(page).toHaveURL(/\/mypage$/);
  await expect(page.locator("#main-content").getByText("traveler@example.com", { exact: true })).toBeVisible();
  await expect(page.getByText("서버에 저장돼 있어요. 복구 메일은 아직 보내지 않아요(준비 중).")).toBeVisible();
  const [sent] = await profileCalls(server, "PUT");
  expect(sent.body).toEqual({ recovery_email: "traveler@example.com" });
  expect(sent.key).toBe("acop_u_known");

  // The server's value is what the app reads when it opens: change it behind the page's back, then reload.
  await request.put(`${STUB}/v1/web/profile`, { headers: { "X-User-Key": "acop_u_known" }, data: { recovery_email: "other@example.com" } });
  await page.reload();
  await expect(page.locator("#main-content").getByText("other@example.com", { exact: true })).toBeVisible();
  expect((await profileCalls(server, "GET")).length).toBeGreaterThan(0);

  // Blank removes it on the server.
  await page.getByRole("link", { name: "수정", exact: true }).click();
  await email(page).fill("");
  await save(page).click();
  await expect(page).toHaveURL(/\/mypage$/);
  await expect(page.getByText("등록된 이메일이 없습니다.", { exact: true })).toBeVisible();
  expect((await profileCalls(server, "PUT")).at(-1)?.body).toEqual({ recovery_email: null });
});

test("사용자 키가 아직 없으면 서버를 부르지 않고(새 사용자를 만들지 않고) 브라우저에 두었다가, 키가 생기면 올린다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page, null);
  await page.goto("/mypage/edit");
  await email(page).fill("early@example.com");
  await save(page).click();
  await expect(page).toHaveURL(/\/mypage$/);
  await expect(page.locator("#main-content").getByText("early@example.com", { exact: true })).toBeVisible();
  await expect(page.getByText("이 브라우저에만 있어요. 첫 여행을 등록하면 서버에 저장돼요. 복구 메일은 아직 보내지 않아요.")).toBeVisible();
  expect(await profileCalls(server, "PUT")).toHaveLength(0);
  expect(await page.evaluate(() => localStorage.getItem("tripilot.web.user-key.v1"))).toBeNull();   // no server user was created for it

  // The first trip's registration issues the key; the app then sends the waiting email.
  await page.evaluate(() => { localStorage.setItem("tripilot.web.user-key.v1", "acop_u_known"); window.dispatchEvent(new Event("tripilot:key-changed")); });
  await expect.poll(async () => (await profileCalls(server, "PUT")).length).toBe(1);
  expect((await profileCalls(server, "PUT"))[0].body).toEqual({ recovery_email: "early@example.com" });
  await expect(page.getByText("서버에 저장돼 있어요. 복구 메일은 아직 보내지 않아요(준비 중).")).toBeVisible();
});

test("서버가 이메일을 거절하면 오류를 알리고 아무것도 바꾸지 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ profile: "reject" });
  await start(page);
  await page.goto("/mypage/edit");
  await email(page).fill("nope@example.com");
  await save(page).click();
  await expect(page.getByRole("alert").filter({ hasText: "이메일 형식이 맞지 않아요." })).toBeVisible();
  await expect(page).toHaveURL(/\/mypage\/edit$/);
  expect(await page.evaluate(() => localStorage.getItem("tripilot.web.contact.v1"))).toBeNull();
  await page.goto("/mypage");
  await expect(page.getByText("등록된 이메일이 없습니다.", { exact: true })).toBeVisible();
});

test("이 호출이 없는 옛 서버면 오류 없이 브라우저에 두고 그렇게 알린다", async ({ page, request }) => {
  await mockServer(request).scenario({ profile: "off" });
  await start(page);
  await page.goto("/mypage/edit");
  await email(page).fill("old@example.com");
  await save(page).click();
  await expect(page).toHaveURL(/\/mypage$/);
  await expect(page.locator("#main-content").getByText("old@example.com", { exact: true })).toBeVisible();
  await expect(page.getByText("이 브라우저에만 있어요. 첫 여행을 등록하면 서버에 저장돼요. 복구 메일은 아직 보내지 않아요.")).toBeVisible();
});
