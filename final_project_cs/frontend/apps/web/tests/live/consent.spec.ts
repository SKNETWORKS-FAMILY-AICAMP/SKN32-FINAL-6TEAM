import { createHash } from "node:crypto";
import { expect, test } from "@playwright/test";
import { docText } from "../../src/features/consent/terms-text";
import { TERMS_DOCS, TERMS_VERSION } from "../../src/features/consent/terms-content";
import { agree, agreeTerms, CONSENT_STORAGE, mockServer, start, useKorean } from "./helpers";

/**
 * `[2026-10-05 사용자 지시]` 약관 동의: 항목별(필수 둘 · 선택 셋)로 받고, 서버 DB 기록에 남기고, 필수에 동의해야 앱을 쓸 수 있다.
 * mock 서버 시험(화면 반응) - 화면이 무엇을 보내고 서버 기록과 어떻게 맞추는지를 본다. 실제 서버의 DB 기록과 게이트는 서버 시험·실서버 확인이 따로 본다.
 * 약관 글 자체(법무 검토 전 초안)의 내용은 여기서 보지 않는다 - `terms-content.test.ts`.
 */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const sha256 = (text: string) => createHash("sha256").update(text, "utf8").digest("hex");
const startCard = (page: import("@playwright/test").Page) => page.getByRole("button", { name: /약관 동의/ });

test("처음 온 사람은 다른 화면으로 가도 약관 화면으로 돌아오고, 약관 화면에는 필수 둘 · 선택 셋과 초안 표시가 있다", async ({ page }) => {
  await useKorean(page);                                                                 // 세션도 동의도 없는 첫 방문
  await page.goto("/mypage");
  await expect(page).toHaveURL(/\/start$/);
  await startCard(page).click();
  const items = page.getByRole("list", { name: "동의 항목" }).getByRole("listitem");
  await expect(items).toHaveCount(5);
  await expect(items.nth(0)).toContainText("[필수]");
  await expect(items.nth(1)).toContainText("[필수]");
  for (const at of [2, 3, 4]) await expect(items.nth(at)).toContainText("[선택]");
  await expect(page.getByRole("note").first()).toContainText("AI 작성 초안");                // 법무 검토 전이라는 것을 숨기지 않는다
  await expect(page.locator('[data-doc="privacy"] label')).toContainText("저는 만 14세 이상입니다");   // 만 14세 미만은 쓸 수 없다 - 동의할 때 확인
});

test("동의하고 다음으로를 누르면 다섯 항목이 서버에 기록된다: 고른 것만 true, 본 한국어 글의 지문(sha256)과 함께", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ consents: "on" });
  await useKorean(page);
  await page.goto("/start");
  await startCard(page).click();
  await agreeTerms(page, ["location"]);
  await expect(page.getByRole("button", { name: /여행 취향 알아보기/ })).toHaveAttribute("aria-expanded", "true");

  await expect.poll(async () => (await server.received("POST", "/v1/web/consents")).length).toBe(1);
  const [post] = await server.received("POST", "/v1/web/consents");
  const body = post.body as { version: string; items: { code: string; agreed: boolean; text_sha256: string }[] };
  expect(body.version).toBe(TERMS_VERSION);
  expect(body.items.map((item) => [item.code, item.agreed])).toEqual([["service_terms", true], ["privacy", true], ["sensitive", false], ["location", true], ["alert_channel", false]]);
  for (const item of body.items) {
    const doc = TERMS_DOCS.find((entry) => entry.code === item.code)!;
    expect(item.text_sha256).toBe(sha256(docText(doc)));                                   // 브라우저가 계산한 지문 = 정본 글에서 계산한 지문
  }
  const stored = JSON.parse(await page.evaluate((key) => localStorage.getItem(key) ?? "null", CONSENT_STORAGE)) as { version: string; synced: boolean; items: Record<string, boolean> };
  expect(stored).toMatchObject({ version: TERMS_VERSION, synced: true, items: { service_terms: true, privacy: true, location: true, sensitive: false } });
});

test("선택 항목을 하나도 안 골라도 필수 둘만으로 앱을 쓸 수 있다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ consents: "on" });
  await useKorean(page);
  await page.goto("/start");
  await startCard(page).click();
  await agreeTerms(page);
  await expect.poll(async () => (await server.received("POST", "/v1/web/consents")).length).toBe(1);
  const [post] = await server.received("POST", "/v1/web/consents");
  expect((post.body as { items: { code: string; agreed: boolean }[] }).items.filter((item) => item.agreed).map((item) => item.code)).toEqual(["service_terms", "privacy"]);
  await page.goto("/mypage");
  await expect(page).toHaveURL(/\/mypage$/);                                              // 문이 열려 있다
});

test("옛 서버(동의 기록을 모름, 404)에서도 동의는 이 브라우저에 남고 앱은 열린다", async ({ page }) => {
  await useKorean(page);                                                                  // 장면 consents 는 기본값 off
  await page.goto("/start");
  await startCard(page).click();
  await agreeTerms(page);
  await page.goto("/mypage");
  await expect(page).toHaveURL(/\/mypage$/);
});

test("서버에 동의 기록이 있으면 이 브라우저에 사본이 없어도 앱이 열리고, 선택 항목은 서버 기록대로 보인다(서버가 이긴다)", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ consents: "on" });
  await server.consents({ service_terms: true, privacy: true, location: true });
  await start(page, "acop_u_known", false);                                              // 세션은 있고 이 브라우저에는 동의 사본이 없다(다른 기기에서 동의함)
  await page.goto("/mypage");
  await expect(page.getByRole("heading", { name: "약관 동의 관리" })).toBeVisible();
  await expect(page).toHaveURL(/\/mypage$/);
  await expect(page.locator('[data-doc="location"]')).toContainText("동의함");
  await expect(page.locator('[data-doc="sensitive"]')).toContainText("동의 안 함");
});

test("다른 기기에서 필수 동의를 철회했으면 이 브라우저의 사본이 있어도 약관 화면으로 돌아간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ consents: "on" });
  await server.consents({ service_terms: true, privacy: false });
  await start(page);                                                                       // 사본은 필수 둘 동의
  await page.goto("/mypage");
  await expect(page).toHaveURL(/\/start$/);
});

test("서버가 동의 없이는 막는데(gate) 이 브라우저에 사본만 있으면, 사본을 서버에 기록하고 통과한다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ consents: "gate" });
  await start(page);                                                                       // 사본은 있고 서버 기록은 없다(예: 오프라인에서 동의했다)
  await page.goto("/mypage");
  await expect(page.getByRole("heading", { name: "약관 동의 관리" })).toBeVisible();
  await expect.poll(async () => (await server.received("POST", "/v1/web/consents")).length).toBe(1);   // 사본을 서버에 한 번 기록했다(통과는 그 뒤에도 이어진다)
});

test("서버가 필수 동의가 없다고 막으면(403 consent_required) 약관 화면으로 보낸다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ consents: "gate" });
  await server.consents({ service_terms: false, privacy: false });                       // 서버에는 「동의 안 함」 기록이 있다
  await start(page);
  await page.goto("/trips");                                                               // 다른 화면이 서버를 부르는 순간 막힌다
  await expect(page).toHaveURL(/\/start$/);
});

test("서버의 약관이 이 화면보다 새 버전이면 새로 고침을 안내한다(옛 약관으로 동의를 받지 않는다)", async ({ page, request }) => {
  await mockServer(request).scenario({ consents: "server_ahead" });
  await start(page);
  await page.goto("/mypage");
  await expect(page.locator("main[role=alert]")).toContainText("약관이 새로 바뀌었어요");
});

test.describe("마이페이지의 약관 동의 관리", () => {
  test("선택 항목은 언제든 켜고 끌 수 있고, 바꿀 때마다 서버에 기록된다(철회도 새 기록)", async ({ page, request }) => {
    const server = mockServer(request);
    await server.scenario({ consents: "on" });
    await start(page);
    await page.goto("/mypage");
    const row = page.locator('[data-doc="location"]');
    await expect(row).toContainText("동의 안 함");
    await row.getByRole("button", { name: "동의하기" }).click();
    await expect(row).toContainText("동의함");
    await expect(row.getByRole("status")).toContainText("동의를 기록했어요");
    await row.getByRole("button", { name: "동의 철회" }).click();
    await expect(row.getByRole("alert")).toContainText("내 위치 기록을 지워요");          // 철회하면 무엇이 사라지는지 먼저 말한다
    await row.getByRole("button", { name: "철회하기" }).click();
    await expect(row).toContainText("동의 안 함");
    await expect(row.getByRole("status")).toContainText("철회했어요");
    const posts = await server.received("POST", "/v1/web/consents");
    // 화면이 열릴 때 서버에 없던 사본을 한 번 보낸 기록이 앞에 있다 - 고객이 바꾼 두 번(켬 → 끔)이 그 뒤에 새 기록으로 쌓인다
    expect(posts.slice(-2).map((entry) => (entry.body as { items: { code: string; agreed: boolean }[] }).items.find((item) => item.code === "location")?.agreed)).toEqual([true, false]);
  });

  test("필수 동의를 철회하면 서비스를 쓸 수 없다는 것을 먼저 말하고, 철회하면 약관 화면으로 간다", async ({ page, request }) => {
    const server = mockServer(request);
    await server.scenario({ consents: "on" });
    await start(page);
    await page.goto("/mypage");
    const row = page.locator('[data-doc="privacy"]');
    await row.getByRole("button", { name: "동의 철회" }).click();
    await expect(row.getByRole("alert")).toContainText("서비스를 쓸 수 없어요");
    await row.getByRole("button", { name: "철회하기" }).click();
    await expect(page).toHaveURL(/\/start$/);
    const posts = await server.received("POST", "/v1/web/consents");
    expect((posts.at(-1)!.body as { items: { code: string; agreed: boolean }[] }).items.find((item) => item.code === "privacy")?.agreed).toBe(false);          // 마지막 기록이 철회
  });

  test("약관 전문을 다시 읽을 수 있다(읽기만, 동의 단추 없음)", async ({ page, request }) => {
    await mockServer(request).scenario({ consents: "on" });
    await start(page);
    await page.goto("/mypage");
    await page.locator('[data-doc="privacy"]').getByRole("button", { name: "전문 보기" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("개인정보");
    await expect(dialog.getByRole("checkbox")).toHaveCount(0);
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
  });
});

test("알림 채널(디스코드·텔레그램)을 연결하려는 순간에야 선택 동의를 받고, 동의 없이는 연결 단추가 없다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ consents: "on", discordConnect: "on", telegram: "on" });
  await start(page);                                                                       // 필수만 동의, 알림 채널은 아직
  await page.goto("/mypage");
  const prompt = page.getByRole("group", { name: /알림 채널/ }).first();
  await expect(prompt).toBeVisible();
  await expect(page.getByRole("button", { name: "디스코드로 연결" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "텔레그램으로 연결" })).toHaveCount(0);
  await expect(prompt).toContainText("동의하지 않아도 앱은 그대로 쓸 수 있어요");
  await prompt.getByRole("button", { name: /에 동의하고 계속/ }).click();
  await expect(page.getByRole("button", { name: "디스코드로 연결" })).toBeVisible();
  await expect(page.getByRole("button", { name: "텔레그램으로 연결" })).toBeVisible();
  const posts = await server.received("POST", "/v1/web/consents");
  expect((posts.at(-1)!.body as { items: { code: string; agreed: boolean }[] }).items.find((item) => item.code === "alert_channel")?.agreed).toBe(true);
});

test("알림 채널 동의를 철회하면 연결해 둔 웹훅이 지워진 것으로 다시 읽힌다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ consents: "on", discordConnect: "on" });
  await agree(page, { alert_channel: true });
  await start(page);
  await page.goto("/mypage");
  await page.getByRole("button", { name: "디스코드로 연결" }).click();                       // mock 디스코드 창을 거쳐 돌아온다
  await expect(page.getByRole("button", { name: "시험 메시지 보내기" })).toBeVisible();
  const row = page.locator('[data-doc="alert_channel"]');
  await row.getByRole("button", { name: "동의 철회" }).click();
  await row.getByRole("button", { name: "철회하기" }).click();
  await expect(page.getByRole("button", { name: "시험 메시지 보내기" })).toHaveCount(0);   // 서버가 웹훅을 지웠고 화면이 다시 읽었다
  await expect(page.getByText("알림을 받을 채널을 연결하려면 알림 채널 정보 수집·이용에 동의해야 해요.")).toBeVisible();
});
