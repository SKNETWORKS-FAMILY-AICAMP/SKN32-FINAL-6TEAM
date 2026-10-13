import { createHash } from "node:crypto";
import { expect, test } from "@playwright/test";
import { docText } from "../../src/features/consent/terms-text";
import { TERMS_DOCS, TERMS_VERSION } from "../../src/features/consent/terms-content";
import { agree, agreeTerms, CONSENT_STORAGE, mockServer, start, useKorean } from "./helpers";

/**
 * `[2026-10-05 사용자 지시]` 약관 동의: 항목별(필수 둘 · 선택 넷)로 받고, 서버 DB 기록에 남기고, 필수에 동의해야 앱을 쓸 수 있다.
 * mock 서버 시험(화면 반응) - 화면이 무엇을 보내고 서버 기록과 어떻게 맞추는지를 본다. 실제 서버의 DB 기록과 게이트는 서버 시험·실서버 확인이 따로 본다.
 * 약관 글 자체(법무 검토 전 초안)의 내용은 여기서 보지 않는다 - `terms-content.test.ts`.
 */
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

const sha256 = (text: string) => createHash("sha256").update(text, "utf8").digest("hex");
const startCard = (page: import("@playwright/test").Page) => page.getByRole("button", { name: /약관 동의/ });

test("처음 온 사람은 다른 화면으로 가도 약관 화면으로 돌아오고, 약관 화면에는 필수 둘 · 선택 넷과 초안 표시가 있다", async ({ page }) => {
  await useKorean(page);                                                                 // 세션도 동의도 없는 첫 방문
  await page.goto("/mypage/consents");
  await expect(page).toHaveURL(/\/start\?terms=required$/);
  await expect(startCard(page)).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByRole("status").filter({ hasText: "이용을 위해서는 필수 약관 동의가 필요해요." })).toBeVisible();
  if (process.env.LOADING_SHOTS) await page.screenshot({ path: `${process.env.LOADING_SHOTS}/04-required-terms.png`, fullPage: true });
  const items = page.getByRole("list", { name: "동의 항목" }).locator(":scope > li");                // 항목 줄만(전문 상자 안의 목록은 제외)
  await expect(items).toHaveCount(6);
  await expect(items.nth(0)).toContainText("[필수]");
  await expect(items.nth(1)).toContainText("[필수]");
  for (const at of [2, 3, 4, 5]) await expect(items.nth(at)).toContainText("[선택]");
  await expect(page.getByText("AI 작성 초안")).toHaveCount(0);                                  // `[2026-10-07 사용자 결정]` 보관 기간을 확정하고 안내문은 내렸다
  await expect(page.getByText(/【확정 필요/)).toHaveCount(0);                                     // 빈칸이 남지 않았다
  await expect(page.locator('[data-doc="privacy"] label')).toContainText("저는 만 14세 이상입니다");   // 만 14세 미만은 쓸 수 없다 - 동의할 때 확인
});

test("동의하고 다음으로를 누르면 여섯 항목이 서버에 기록된다: 고른 것만 true, 본 한국어 글의 지문(sha256)과 함께", async ({ page, request }) => {
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
  expect(body.items.map((item) => [item.code, item.agreed])).toEqual([["service_terms", true], ["privacy", true], ["sensitive", false], ["location", true], ["alert_channel", false]]);   // `[2026-10-12 임시]` service_improvement 는 서버가 아직 몰라 보내지 않는다
  for (const item of body.items) {
    const doc = TERMS_DOCS.find((entry) => entry.code === item.code)!;
    expect(item.text_sha256).toBe(sha256(docText(doc)));                                   // 브라우저가 계산한 지문 = 정본 글에서 계산한 지문
  }
  const stored = JSON.parse(await page.evaluate((key) => localStorage.getItem(key) ?? "null", CONSENT_STORAGE)) as { version: string; synced: boolean; items: Record<string, boolean> };
  expect(stored).toMatchObject({ version: TERMS_VERSION, synced: true, items: { service_terms: true, privacy: true, location: true, sensitive: false } });
});

test("관리자가 보관 기간을 고친 cs 프로젝트 서버면 약관 글에 서버의 기간이 실리고, 동의는 서버의 약관 버전과 그 글의 지문으로 기록된다", async ({ page, request }) => {
  // `[2026-10-07 사용자 결정]` 보관 기간은 관리자 화면에서 고칠 수 있다 - 고치면 서버의 약관 버전이 `<기본>+ret<N>` 이 되고, 웹이 옛 버전으로 보내면 409 가 난다.
  const server = mockServer(request);
  await server.scenario({ consents: "on", retention: "on" });
  await useKorean(page);
  await page.goto("/start");
  await startCard(page).click();
  const privacyText = page.locator('li[data-doc="privacy"]').getByRole("region");
  await expect(privacyText).toContainText("마지막 이용 후 2년이 지나면 파기");                 // 서버가 준 문장(웹 기본값은 1년)
  await agreeTerms(page, []);
  await expect.poll(async () => (await server.received("POST", "/v1/web/consents")).length).toBe(1);
  const [post] = await server.received("POST", "/v1/web/consents");
  const body = post.body as { version: string; items: { code: string; text_sha256: string }[] };
  expect(body.version).toBe(`${TERMS_VERSION}+ret1`);
  const privacyDefault = sha256(docText(TERMS_DOCS.find((entry) => entry.code === "privacy")!));
  expect(body.items.find((item) => item.code === "privacy")!.text_sha256).not.toBe(privacyDefault);   // 본 글이 기본값 글과 다르니 지문도 다르다
  expect((await server.received("GET", "/v1/web/legal/retention")).length).toBeGreaterThan(0);
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
  await page.goto("/mypage/consents");
  await expect(page).toHaveURL(/\/mypage\/consents$/);                                              // 문이 열려 있다
});

test("옛 서버(동의 기록을 모름, 404)에서도 동의는 이 브라우저에 남고 앱은 열린다", async ({ page }) => {
  await useKorean(page);                                                                  // 장면 consents 는 기본값 off
  await page.goto("/start");
  await startCard(page).click();
  await agreeTerms(page);
  await page.goto("/mypage/consents");
  await expect(page).toHaveURL(/\/mypage\/consents$/);
});

test("서버에 동의 기록이 있으면 이 브라우저에 사본이 없어도 앱이 열리고, 선택 항목은 서버 기록대로 보인다(서버가 이긴다)", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ consents: "on" });
  await server.consents({ service_terms: true, privacy: true, location: true });
  await start(page, "acop_u_known", false);                                              // 세션은 있고 이 브라우저에는 동의 사본이 없다(다른 기기에서 동의함)
  await page.goto("/mypage/consents");
  await expect(page.getByRole("heading", { name: "약관 동의 관리" })).toBeVisible();
  await expect(page).toHaveURL(/\/mypage\/consents$/);
  await page.getByRole("button", { name: "선택 약관 동의", exact: true }).click();
  await expect(page.locator('[data-doc="location"]')).toContainText("동의함");
  await expect(page.locator('[data-doc="sensitive"]')).toContainText("동의 안 함");
});

test("다른 기기에서 필수 동의를 철회했으면 이 브라우저의 사본이 있어도 약관 화면으로 돌아간다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ consents: "on" });
  await server.consents({ service_terms: true, privacy: false });
  await start(page);                                                                       // 사본은 필수 둘 동의
  await page.goto("/mypage/consents");
  await expect(page).toHaveURL(/\/start\?terms=required$/);
});

test("서버가 동의 없이는 막는데(gate) 이 브라우저에 사본만 있으면, 사본을 서버에 기록하고 통과한다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ consents: "gate" });
  await start(page);                                                                       // 사본은 있고 서버 기록은 없다(예: 오프라인에서 동의했다)
  await page.goto("/mypage/consents");
  await expect(page.getByRole("heading", { name: "약관 동의 관리" })).toBeVisible();
  await expect.poll(async () => (await server.received("POST", "/v1/web/consents")).length).toBe(1);   // 사본을 서버에 한 번 기록했다(통과는 그 뒤에도 이어진다)
});

test("서버가 필수 동의가 없다고 막으면(403 consent_required) 약관 화면으로 보낸다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ consents: "gate" });
  await server.consents({ service_terms: false, privacy: false });                       // 서버에는 「동의 안 함」 기록이 있다
  await start(page);
  await page.goto("/trips");                                                               // 다른 화면이 서버를 부르는 순간 막힌다
  await expect(page).toHaveURL(/\/start\?terms=required$/);
});

test("서버의 약관이 이 화면보다 새 버전이면 새로 고침을 안내한다(옛 약관으로 동의를 받지 않는다)", async ({ page, request }) => {
  await mockServer(request).scenario({ consents: "server_ahead" });
  await start(page);
  await page.goto("/mypage/consents");
  await expect(page.getByRole("alert", { name: "약관 확인 진행" })).toContainText("약관이 새로 바뀌었어요");
});

for (const wait of [{ ms: 500, visible: false }, { ms: 1200, visible: true }]) {
  test(`동의 응답 ${wait.ms}ms 대기에서는 준비 안내가 ${wait.visible ? "나타나고 응답 후 닫힌다" : "나타나지 않는다"}`, async ({ page, request }) => {
    const server = mockServer(request);
    await server.scenario({ consents: "on", consentStream: "json" });
    await server.consents({ service_terms: true, privacy: true });
    await start(page);
    const clockStart = new Date("2026-10-12T12:00:00+09:00");
    await page.clock.install({ time: clockStart });
    await page.clock.pauseAt(new Date(clockStart.getTime() + 1000));
    let release!: () => void;
    let received!: () => void;
    const held = new Promise<void>((resolve) => { release = resolve; });
    const requested = new Promise<void>((resolve) => { received = resolve; });
    await page.route("**/v1/web/consents", async (route) => {
      if (route.request().method() !== "GET") return route.continue();
      received();
      await held;
      await route.continue();
    });
    try {
      await page.goto("/mypage");
      await requested;
      const progress = page.getByRole("status", { name: "약관 확인 진행" });
      await page.clock.runFor(wait.ms);
      await expect(progress).toHaveCount(wait.visible ? 1 : 0);
      await expect(page.getByRole("heading", { name: "마이페이지", exact: true })).toBeVisible();
      release();
      await expect(progress).toHaveCount(0);
      await expect.poll(async () => (await server.received("GET", "/v1/web/consents")).length).toBeGreaterThan(0);
    } finally {
      release();
    }
  });
}

test("약관 SSE를 기다려도 마이페이지는 남고 실제 단계와 완료 수를 기존 화면 위에 보인다", async ({ page, request, context }) => {
  const server = mockServer(request);
  await server.scenario({ consents: "on", retention: "on", consentStream: "slow" });
  await server.consents({ service_terms: true, privacy: true });
  await start(page);
  // `[2026-10-13]` 안내는 확인이 1초를 넘어야 뜨고(바로 위 시험이 본다) mock 단계는 1.2초씩이라, 「동의 기록 읽기」가 보이는 틈이
  // 약 0.27초뿐이었다 — 로컬 · GitHub CI 모두 그 틈을 놓쳐 늘 실패했다. 스트림 요청이 나간 뒤 1초 지연만 바로 넘겨 단계마다 약 1.2초 보이게 한다.
  await page.clock.install();
  const accepts: string[] = [];
  page.on("request", (req) => { if (req.url().endsWith("/v1/web/consents") && req.method() === "GET") accepts.push(req.headers().accept); });
  await page.goto("/mypage");
  await expect.poll(() => accepts.length).toBeGreaterThan(0);
  await page.clock.runFor(1000);
  const progress = page.getByRole("status", { name: "약관 확인 진행" });
  await expect(progress.locator('[aria-current="step"]')).toContainText("동의 기록 읽기");
  await expect(progress).toContainText("2/6단계 완료");
  await expect(page.getByRole("heading", { name: "마이페이지", exact: true })).toBeVisible();
  await expect(page.locator('[data-consent-shell]')).toHaveCount(0);
  await expect(progress.locator('[aria-current="step"]')).toContainText("약관 버전 확인");
  await expect(progress).toContainText("3/6단계 완료");
  if (process.env.CONSENT_SHOTS) {
    await page.screenshot({ path: `${process.env.CONSENT_SHOTS}/consent-progress-desktop.png`, fullPage: true });
    await page.setViewportSize({ width: 375, height: 812 });
    await page.screenshot({ path: `${process.env.CONSENT_SHOTS}/consent-progress-mobile.png`, fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await expect(progress.locator('[aria-current="step"]')).toContainText("필수 항목 확인");
  await expect(progress).toContainText("4/6단계 완료");
  await expect(progress).toHaveCount(0);
  expect(accepts.length).toBeGreaterThan(0);
  expect(accepts.every((value) => value === "text/event-stream")).toBe(true);
  expect(context.pages()).toHaveLength(1);
  await expect(page).toHaveURL(/\/mypage$/);
});

test("동의 사본 없이 확인하는 첫 화면은 열린 약관이고, 보호 조회는 동의 확인이 끝난 다음 시작한다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ consents: "on", consentStream: "slow" });
  await server.consents({ service_terms: true, privacy: true });
  await start(page, "acop_u_known", false);
  await page.goto("/mypage/consents");
  await expect(page.getByText("이용을 위해서는 필수 약관 동의가 필요해요.")).toBeVisible();
  await expect(startCard(page)).toHaveAttribute("aria-expanded", "true");
  expect((await server.received("GET", "/v1/web/profile")).length).toBe(0);
  await expect(page.getByRole("heading", { name: "약관 동의 관리" })).toBeVisible();
  await expect(page.getByText("이용을 위해서는 필수 약관 동의가 필요해요.")).toHaveCount(0);
});

test("동의 조회 실패를 미동의로 바꾸지 않고 같은 화면에서 다시 확인한다", async ({ page, request }) => {
  const server = mockServer(request);
  await server.scenario({ consents: "on", consentStream: "fail" });
  await server.consents({ service_terms: true, privacy: true });
  await start(page, "acop_u_known", false);
  await page.goto("/mypage/consents");
  const error = page.getByRole("alert", { name: "약관 확인 진행" });
  await expect(error).toContainText("동의 기록을 확인하지 못했어요");
  await expect(page).toHaveURL(/\/mypage\/consents$/);
  await server.scenario({ consentStream: "on" });
  await error.getByRole("button", { name: "다시 확인하기" }).click();
  await expect(page.getByRole("heading", { name: "약관 동의 관리" })).toBeVisible();
  await expect(error).toHaveCount(0);
  await expect(page).toHaveURL(/\/mypage\/consents$/);
});

test.describe("마이페이지의 약관 동의 관리(`[2026-10-13]` /mypage/consents)", () => {
  // `[2026-10-12 임시]` 서버가 아직 service_improvement 를 기록하지 못해(보내면 저장 전체가 422) 화면은 전문만 보이고 동의 · 철회는 「준비 중」이다.
  //   서버가 받게 되면 `SERVER_PENDING_CONSENTS` 에서 빼고 이 시험을 옛 모양(켜고 철회 → 보낸 값 [true, false])으로 되돌린다.
  test("서비스 개선 선택 동의는 서버가 받기 전까지 준비 중이며 서버에 보내지 않는다", async ({ page, request }) => {
    const server = mockServer(request);
    await server.scenario({ consents: "on" });
    await start(page);
    await page.goto("/mypage/consents");
    await page.getByRole("button", { name: "선택 약관 동의", exact: true }).click();
    const row = page.locator('[data-doc="service_improvement"]');
    await expect(row).toContainText("준비 중");
    await expect(row.getByRole("button", { name: "동의하기" })).toHaveCount(0);
    await expect(row.getByRole("button", { name: "동의 철회" })).toHaveCount(0);
    await row.getByRole("button", { name: "전문 보기" }).click();
    await expect(row.locator("[data-optional-full]")).toBeVisible();
    await expect(page).toHaveURL(/\/mypage\/consents$/);
    const posts = await server.received("POST", "/v1/web/consents");
    for (const entry of posts) expect((entry.body as { items: { code: string }[] }).items.some((item) => item.code === "service_improvement")).toBe(false);
    if (process.env.CONSENT_SHOTS) {
      await page.screenshot({ path: `${process.env.CONSENT_SHOTS}/improvement-desktop.png`, fullPage: true });
      await page.setViewportSize({ width: 375, height: 812 });
      await page.screenshot({ path: `${process.env.CONSENT_SHOTS}/improvement-mobile.png`, fullPage: true });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    }
  });
  test("선택 항목은 언제든 켜고 끌 수 있고, 바꿀 때마다 서버에 기록된다(철회도 새 기록)", async ({ page, request }) => {
    const server = mockServer(request);
    await server.scenario({ consents: "on" });
    await start(page);
    await page.goto("/mypage/consents");
    await page.getByRole("button", { name: "선택 약관 동의", exact: true }).click();
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

  test("필수 항목 요약과 철회는 관리 목록에서 빼고 선택 넷만 수정한다", async ({ page, request }) => {
    await mockServer(request).scenario({ consents: "on" });
    await start(page);
    await page.goto("/mypage/consents");
    await page.getByRole("button", { name: "선택 약관 동의", exact: true }).click();
    await expect(page.getByRole("list", { name: "선택 동의 항목" }).locator(":scope > li")).toHaveCount(4);
    await expect(page.locator('[data-doc="service_terms"], [data-doc="privacy"]')).toHaveCount(0);
    await expect(page.getByRole("button", { name: "약관 전문 확인" })).toBeVisible();
  });

  test("약관 전문을 다시 읽을 수 있다(읽기만, 동의 단추 없음)", async ({ page, request }) => {
    await mockServer(request).scenario({ consents: "on" });
    await start(page);
    await page.goto("/mypage/consents");
    await page.getByRole("button", { name: "약관 전문 확인" }).click();
    await page.getByRole("navigation", { name: "필수 약관 선택" }).getByRole("button", { name: /개인정보/ }).click();
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
  await page.goto("/mypage/alerts");                                                       // `[2026-10-13 마이페이지 A안]` 알림 채널은 「알림 받는 곳」 화면
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
  // `[2026-10-13 마이페이지 A안]` 연결은 「알림 받는 곳」, 철회는 「약관 · 동의」 화면 — 철회 뒤 알림 화면을 다시 열면 서버가 지운 대로 읽는다.
  await page.goto("/mypage/alerts");
  await page.getByRole("button", { name: "디스코드로 연결" }).click();                       // mock 디스코드 창을 거쳐 돌아온다(마이페이지가 알림 화면으로 넘긴다)
  await expect(page).toHaveURL(/\/mypage\/alerts$/);
  await expect(page.getByRole("button", { name: "시험 메시지 보내기" })).toBeVisible();
  await page.goto("/mypage/consents");
  await page.getByRole("button", { name: "선택 약관 동의", exact: true }).click();
  const row = page.locator('[data-doc="alert_channel"]');
  await row.getByRole("button", { name: "동의 철회" }).click();
  await row.getByRole("button", { name: "철회하기" }).click();
  await expect(row).toContainText("동의 안 함");
  await page.goto("/mypage/alerts");
  await expect(page.getByRole("button", { name: "시험 메시지 보내기" })).toHaveCount(0);   // 서버가 웹훅을 지웠다
  await expect(page.getByText("알림을 받을 채널을 연결하려면 알림 채널 정보 수집·이용에 동의해야 해요.")).toBeVisible();
});
