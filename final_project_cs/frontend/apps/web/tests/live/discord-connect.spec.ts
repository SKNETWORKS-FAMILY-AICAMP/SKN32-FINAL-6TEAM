import { expect, test, type Page } from "@playwright/test";
import { mockServer, start } from "./helpers";

/**
 * `[2026-10-05 사용자 지시]` 마이페이지 「디스코드로 연결」 — 웹훅 주소를 복사해 붙여넣는 대신 디스코드 창에서 서버·채널을 고르면 서버가 웹훅을 받아 저장한다.
 * mock 서버 시험이다: 화면이 무엇을 보내고 돌아온 뒤 어떻게 반응하는지를 본다(디스코드 창은 mock 서버의 `/__test/discord-connect`). 실제 디스코드가
 * 서버에 웹훅을 넘기는 것은 이 시험이 보지 않는다 — 실서버 확인이 따로 본다.
 */
const MASKED = "https://discord.com/api/web" + "hooks/1234…/••••";
const SECRET = "abcdefghijklmnopqrstuvwxyz0123456789ABCD";

test.beforeEach(async ({ page, request }) => {
  await mockServer(request).reset();
  await start(page);
});

const connectButton = (page: Page) => page.getByRole("button", { name: "디스코드로 연결" });

test("서버가 연결할 수 있다고 말하지 않으면(옛 서버) 연결 단추가 없고 지금처럼 「웹훅 등록하기」만 있다", async ({ page }) => {
  await page.goto("/mypage");
  await expect(page.getByRole("link", { name: "웹훅 등록하기" })).toBeVisible();
  await expect(connectButton(page)).toHaveCount(0);
});

test("연결 단추를 누르면 디스코드 창을 거쳐 마이페이지로 돌아오고, 웹훅은 서버가 받아 가린 모양으로만 보인다 — 웹은 주소를 다루지 않는다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ discordConnect: "on" });
  await page.goto("/mypage");
  await expect(connectButton(page)).toBeVisible();
  await expect(page.getByText("주소를 복사해 붙여넣을 필요가 없어요", { exact: false })).toBeVisible();
  await expect(page.getByRole("link", { name: "주소 직접 넣기" })).toBeVisible();                       // 직접 넣는 길도 남는다

  await connectButton(page).click();
  await expect(page.getByRole("status").filter({ hasText: "디스코드 채널이 연결됐어요" })).toBeVisible();
  await expect(page).toHaveURL(/\/mypage$/);                                                         // `?discord=…` 는 주소창에 남지 않는다
  await expect(page.getByText(MASKED)).toBeVisible();
  await expect(page.getByRole("button", { name: "시험 메시지 보내기" })).toBeVisible();
  await expect(page.getByRole("button", { name: "다른 채널로 바꾸기" })).toBeVisible();

  expect(await server.received("POST", "/v1/web/profile/discord/connect/start")).toHaveLength(1);
  expect(await server.received("PUT", "/v1/web/profile")).toHaveLength(0);                           // 웹은 주소를 서버에 보내지도 않았다
  expect(await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }))).not.toContain(SECRET);
  await expect(page.locator("body")).not.toContainText(SECRET);

  await page.reload();                                                                                // 새로 고쳐도 같은 메시지가 다시 뜨지 않는다
  await expect(page.getByText(MASKED)).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "디스코드 채널이 연결됐어요" })).toHaveCount(0);
});

test("연결한 뒤 「시험 메시지 보내기」로 확인할 수 있고, 「다른 채널로 바꾸기」는 같은 길을 다시 연다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ discordConnect: "on" });
  await page.goto("/mypage");
  await connectButton(page).click();
  await expect(page.getByText(MASKED)).toBeVisible();
  await page.getByRole("button", { name: "시험 메시지 보내기" }).click();
  await expect(page.getByText("시험 메시지가 도착했어요.")).toBeVisible();

  await page.getByRole("button", { name: "다른 채널로 바꾸기" }).click();
  await expect(page.getByRole("status").filter({ hasText: "디스코드 채널이 연결됐어요" })).toBeVisible();
  expect(await server.received("POST", "/v1/web/profile/discord/connect/start")).toHaveLength(2);
});

for (const [word, text] of [["cancelled", "연결을 취소했어요. 바뀐 것은 없어요."], ["expired", "연결 시간이 지났어요."], ["failed", "디스코드 연결에 실패했어요."]] as const) {
  test(`디스코드 창에서 돌아왔는데 ${word} 이면 이유를 말하고, 웹훅은 그대로 없으며 다시 누를 수 있다`, async ({ page, request }) => {
    await mockServer(request).scenario({ discordConnect: word });
    await page.goto("/mypage");
    await connectButton(page).click();
    await expect(page.getByRole("alert").filter({ hasText: text })).toBeVisible();
    await expect(page).toHaveURL(/\/mypage$/);
    await expect(page.getByText("등록된 웹훅이 없어요.")).toBeVisible();
    await expect(connectButton(page)).toBeEnabled();
  });
}

test("연결 시작이 실패하면 디스코드로 가지 않고 서버 문장을 보인다", async ({ page, request }) => {
  await mockServer(request).scenario({ discordConnect: "start_fails" });
  await page.goto("/mypage");
  await connectButton(page).click();
  await expect(page.getByRole("alert").filter({ hasText: "디스코드 연결을 시작하지 못했어요" })).toBeVisible();
  await expect(page).toHaveURL(/\/mypage$/);
  await expect(connectButton(page)).toBeEnabled();
});

test("서버가 디스코드 것이 아닌 주소를 주면 따라가지 않는다", async ({ page, request }) => {
  await mockServer(request).scenario({ discordConnect: "bad_address" });
  await page.goto("/mypage");
  await connectButton(page).click();
  await expect(page.getByRole("alert").filter({ hasText: "서버가 디스코드 연결 주소를 주지 않았어요." })).toBeVisible();
  await expect(page).toHaveURL(/\/mypage$/);
});

test("수정 화면의 웹훅 칸은 그대로 있고, 더 쉬운 길이 마이페이지에 있다고 알려 준다", async ({ page, request }) => {
  await mockServer(request).scenario({ discordConnect: "on" });
  await page.goto("/mypage/edit");
  await expect(page.getByRole("textbox", { name: "디스코드 웹훅 URL (선택)" })).toBeVisible();
  await expect(page.getByText("「디스코드로 연결」을 쓰면", { exact: false })).toBeVisible();
});
