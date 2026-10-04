import { expect, test, type Page } from "@playwright/test";
import { mockServer, start } from "./helpers";

/**
 * `[2026-10-04 사용자 지시 · 서버 D-CS-012]` 마이페이지 「에이전트 연결」 — 회원만, 키는 만든 직후 한 번만 보인다.
 * mock 서버 시험이다 — 화면이 무엇을 보내고 어떻게 반응하는지를 본다. 서버가 실제로 키를 만들고 폐기하는지는 실서버 확인이 따로 본다.
 */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const card = (page: Page) => page.getByRole("group", { name: "에이전트 연결" });

test("게스트는 키를 만들 수 없다 — 로그인하면 쓸 수 있다고 알리고, 계정을 연결하러 가는 길을 보인다", async ({ page, request }) => {
  const server = mockServer(request);
  await start(page);                                                       // 기본 세션 = 게스트
  await page.goto("/mypage");
  await expect(card(page)).toContainText("로그인한 사용자만 에이전트를 연결할 수 있어요");
  await expect(card(page).getByRole("button", { name: "키 만들기" })).toHaveCount(0);
  await expect(card(page).getByRole("link", { name: /소셜 계정을 연결하면/ })).toHaveAttribute("href", "/mypage#accounts");
  expect(await server.received("GET", "/v1/web/agent-keys")).toHaveLength(0);   // 게스트로는 목록을 묻지도 않는다
});

test("회원: 이름·권한·기간을 정해 키를 만들면 키가 한 번 보이고, 연결 명령은 키를 주소가 아니라 머리말에 싣는다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ sessionKind: "member" });
  await start(page);
  await page.goto("/mypage");
  await expect(card(page)).toContainText("아직 만든 키가 없어요");
  const make = card(page).getByRole("button", { name: "키 만들기" });
  await expect(make).toBeDisabled();                                        // 이름이 없으면 만들 수 없다
  await card(page).getByLabel(/^이름/).fill("내 노트북의 클로드 코드");
  await card(page).getByLabel("읽기·쓰기").check();
  await card(page).getByLabel("유효 기간").selectOption("30");
  await make.click();

  const fresh = card(page).getByRole("status", { name: "새 키" });
  await expect(fresh).toContainText("한 번만 보여요");
  const key = await fresh.getByRole("textbox", { name: "새 에이전트 키" }).inputValue();
  expect(key).toMatch(/^acop_a_/);
  const command = (await fresh.locator("code").textContent()) ?? "";
  expect(command).toContain("claude mcp add --transport http tripilot ");
  expect(command).toContain(`--header "Authorization: Bearer ${key}"`);
  expect(command.split(" ").find((part) => part.startsWith("http"))).not.toContain(key);   // 키는 주소에 없다

  const [sent] = await server.received("POST", "/v1/web/agent-keys");
  expect(sent.body).toEqual({ name: "내 노트북의 클로드 코드", scope: "write", expires_days: 30 });
  expect(sent.csrf).toBe("csrf-known");                                     // 쓰기에는 보안 토큰이 따른다
  expect(sent.key).toBeNull();                                              // 쿠키만 — 키 머리말은 없다

  // 목록에는 키 글자 없이 이름·권한·상태만 있다
  const item = card(page).getByRole("list", { name: "만든 에이전트 키" }).getByRole("listitem").filter({ hasText: "내 노트북의 클로드 코드" });
  await expect(item).toContainText("읽기·쓰기");
  await expect(item).toContainText("사용 중");
  await expect(item).not.toContainText(key);
});

test("키는 화면 상태에만 있다: 브라우저 저장소에 남지 않고, 새로 고치면 다시 볼 수 없다", async ({ page, request }) => {
  await mockServer(request).scenario({ sessionKind: "member" });
  await start(page);
  await page.goto("/mypage");
  await card(page).getByLabel(/^이름/).fill("서버");
  await card(page).getByRole("button", { name: "키 만들기" }).click();
  const fresh = card(page).getByRole("status", { name: "새 키" });
  const key = await fresh.getByRole("textbox", { name: "새 에이전트 키" }).inputValue();

  const stored = await page.evaluate(() => JSON.stringify([...Object.entries(localStorage), ...Object.entries(sessionStorage)]));
  expect(stored).not.toContain(key);

  await fresh.getByRole("button", { name: "따로 보관했어요" }).click();
  await expect(fresh).toHaveCount(0);                                       // 닫으면 사라진다
  await page.reload();
  await expect(card(page).getByRole("list", { name: "만든 에이전트 키" })).toContainText("서버");
  await expect(page.getByText(key)).toHaveCount(0);
  await expect(page.locator(`input[value="${key}"]`)).toHaveCount(0);
});

test("폐기는 두 번 눌러야 한다(폐기 → 폐기하기): 취소하면 아무것도 안 보내고, 폐기하면 서버에 알리고 목록에서 「폐기됨」이 된다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ sessionKind: "member" });
  await start(page);
  await page.goto("/mypage");
  await card(page).getByLabel(/^이름/).fill("쓰던 키");
  await card(page).getByRole("button", { name: "키 만들기" }).click();
  await card(page).getByRole("button", { name: "따로 보관했어요" }).click();

  const item = card(page).getByRole("list", { name: "만든 에이전트 키" }).getByRole("listitem").filter({ hasText: "쓰던 키" });
  await item.getByRole("button", { name: "쓰던 키 폐기" }).click();
  await item.getByRole("button", { name: "취소" }).click();
  expect(await server.received("DELETE", "/v1/web/agent-keys/k-1")).toHaveLength(0);

  await item.getByRole("button", { name: "쓰던 키 폐기" }).click();
  await item.getByRole("button", { name: "폐기하기" }).click();
  await expect(card(page).getByRole("status").filter({ hasText: "키를 폐기했어요" })).toBeVisible();
  await expect(item).toContainText("폐기됨");
  await expect(item.getByRole("button", { name: /폐기$/ })).toHaveCount(0);   // 이미 폐기한 키에는 단추가 없다
  const [gone] = await server.received("DELETE", "/v1/web/agent-keys/k-1");
  expect(gone.csrf).toBe("csrf-known");
});

test("사용 중인 키가 한도(409 agent_key_limit)면 서버 문장 그대로 알리고, 키 글자는 만들어지지 않는다", async ({ page, request }) => {
  await mockServer(request).scenario({ sessionKind: "member", agentKeys: "limit" });
  await start(page);
  await page.goto("/mypage");
  await card(page).getByLabel(/^이름/).fill("열한 번째");
  await card(page).getByRole("button", { name: "키 만들기" }).click();
  await expect(card(page).getByRole("alert")).toContainText("사용 중인 에이전트 키가 10개예요");
  await expect(card(page).getByRole("status", { name: "새 키" })).toHaveCount(0);
});

test("서버가 아직 이 기능을 모르면(404) 「서버가 준비 중」이라고만 말하고 만들 단추를 두지 않는다", async ({ page, request }) => {
  await mockServer(request).scenario({ sessionKind: "member", agentKeys: "off" });
  await start(page);
  await page.goto("/mypage");
  await expect(card(page)).toContainText("에이전트 연결은 서버가 준비 중이에요");
  await expect(card(page).getByRole("button", { name: "키 만들기" })).toHaveCount(0);
});
