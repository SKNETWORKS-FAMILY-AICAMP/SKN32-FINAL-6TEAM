// 소개 화면의 「이용 방법」 그림(public/images/tripilot-guide-<언어>-<번호>-<이름>.jpg)을 실제 화면에서 다시 찍는다.
//
//   왜 있나(2026-10-04 사용자 질문 「패치할 때마다 다시 캡처 안 해도 되잖아」): 화면을 소개에 그대로 끼우면 취향·계획 입력 화면이
//   서버 호출·사람 확인·방문자의 저장 상태를 안고 있어 부작용이 생긴다. 그래서 그림으로 두되, 손으로 찍지 않고 이 스크립트 한 줄로 다시 찍는다.
//
//   쓰는 법:
//     1) 화면 두 장(1 취향 · 2 계획 입력)은 서버가 필요 없다 — 웹 개발 서버(기본 http://127.0.0.1:3100)만 떠 있으면 된다.
//          node scripts/guide-shots.mjs --only 1,2
//     2) 나머지 두 장(3 점검 결과 · 4 채팅)은 여행 자료가 있어야 그려진다. ★실제 서버에 여행을 등록하지 않는다 —
//        mock 서버(tests/live/stub-server.mjs)와 거기에 맞춰 빌드한 웹(.next-live)을 띄워 두고 `--mock` 으로 알려 준다.
//        (등록은 팀 채널에 알림이 가고 자료가 남는다. mock 서버는 같은 입력에 늘 같은 답을 주어 그림도 늘 같다.)
//          STUB_PORT=8143 node tests/live/stub-server.mjs                      # mock 서버
//          LIVE_SKIP_BUILD=1 LIVE_PORT=3202 STUB_PORT=8143 node tests/live/serve.mjs   # 그 서버에 맞춰 빌드된 웹
//          node scripts/guide-shots.mjs --base http://127.0.0.1:3202 --mock http://127.0.0.1:8143
//     --lang ko|en|ko,en · --out <폴더>(먼저 다른 곳에 찍어 눈으로 볼 때. 없으면 public/images 에 바로 쓴다)
//
//   덮어쓰기 전에 옛 그림을 `<저장소>/frontend/_backup/<날짜>_이용방법그림_옛판/` 에 복사해 두는 것은 사람이 한다(전역 규칙).
import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const argv = process.argv.slice(2);
const option = (name) => { const at = argv.indexOf(`--${name}`); return at >= 0 ? argv[at + 1] : undefined; };

const BASE = (option("base") ?? process.env.GUIDE_BASE ?? "http://127.0.0.1:3100").replace(/\/$/, "");
const MOCK = (option("mock") ?? process.env.GUIDE_MOCK ?? "").replace(/\/$/, "");   // mock 서버 주소 — 3·4번 그림에 필요
const HERE = path.dirname(fileURLToPath(import.meta.url));
const WIDTH = 390, SCALE = 2;                   // 780 px 폭 — 소개 화면의 그림 칸(width=780 height=1120)과 같다
const HEIGHT = 560;                             // 그림 한 장의 높이(CSS px) → 1120 px
const OUT = option("out") ? path.resolve(option("out")) : process.env.GUIDE_OUT ?? path.resolve(HERE, "..", "public", "images");

const only = (option("only") ?? (MOCK ? "1,2,3,4" : "1,2")).split(",").map((value) => value.trim());
const languages = (option("lang") ?? "ko,en").split(",").map((value) => value.trim());

const settingsKey = "tripilot.web.settings.v1";
const onboardingKey = "tripilot.web.onboarding.v1";
const blankAnswers = { theme: "", party: "", partyOther: "", priority: [], details: { food: [], activity: [], mobility: [] }, indoorDining: "", indoorActivity: "", onDisruption: "", pace: "", skipped: [] };
const TRIP_ID = "11111111-2222-3333-4444-555555555555";   // mock 서버의 여행(stub-server.mjs 의 TRIP_ID)
const SESSION_COOKIE = "tripilot_sid_dev";                // mock 서버가 아는 세션(returning visitor)

/** 지도 바탕. mock 서버의 타일은 한 점짜리 그림이라 늘어나면 붉은 판이 된다 — 그림에는 잔잔한 바탕을 대신 준다(실제 지도 그림이 아니라 핀을 보이기 위한 바탕이다). */
const TILE_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="#e9eee4"/><path d="M0 92H256M0 190H256M70 0V256M176 0V256" stroke="#f7f9f4" stroke-width="9"/><path d="M0 40L256 130" stroke="#dbe3d3" stroke-width="5"/></svg>';

const mock = async (request, pathname, data) => { const response = await request.post(`${MOCK}${pathname}`, data ? { data } : {}); if (!response.ok()) throw new Error(`mock 서버 ${pathname} → ${response.status()}`); };

const shots = {
  /** 1. 취향 — 첫 질문에서 「맛집 탐방」을 골라 둔 모습. 약관에 동의한 상태로 시작해 취향 카드를 연다. 서버를 쓰지 않는다. */
  "1": async (page, lang) => {
    await page.goto(`${BASE}/start`, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: lang === "ko" ? /여행 취향 알아보기/ : /Your travel preferences/ }).click();
    await page.getByRole("button", { name: lang === "ko" ? "맛집 탐방" : "Food discoveries", exact: true }).click();
    const head = await page.locator('button[aria-expanded="true"]').first().boundingBox();   // 열린 카드의 머리 — 카드는 그 위 22px 쯤에서 시작한다
    return { name: "1-preferences", clip: { x: 0, y: Math.max(0, (head?.y ?? 0) - 22), width: WIDTH, height: HEIGHT } };
  },
  /** 2. 계획 입력 — 「예시 불러오기」로 예시 계획을 채운 모습. 보내지 않는다(서버를 쓰지 않는다). */
  "2": async (page, lang) => {
    await page.goto(`${BASE}/trips/new`, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: lang === "ko" ? "예시 불러오기" : /Load example/i }).first().click();
    await page.waitForFunction(() => [...document.querySelectorAll("textarea")].some((area) => area.value.length > 20));
    const box = await page.locator("main").first().boundingBox();
    return { name: "2-plan", clip: { x: 0, y: box?.y ?? 0, width: WIDTH, height: HEIGHT } };
  },
  /** 3. 점검 결과 — 예시 계획을 보내 읽힌 뒤의 확인 화면(고칠 곳이 있는 판). mock 서버가 필요하다. */
  "3": async (page, lang, context) => {
    await mock(context.request, "/__test/reset");
    await mock(context.request, "/__test/scenario", { review: "on", board: "rich", readingPolls: 0, intakeDelay: 0, intakeEvents: "on", intakeProgress: "on" });
    await context.route("**/__test/tile/**", (route) => route.fulfill({ contentType: "image/svg+xml", body: TILE_SVG }));
    await page.setViewportSize({ width: WIDTH, height: HEIGHT });
    await page.goto(`${BASE}/trips/new`, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: lang === "ko" ? "예시 불러오기" : /Load example/i }).first().click();
    await page.waitForFunction(() => [...document.querySelectorAll("textarea")].some((area) => area.value.length > 20));
    await page.getByRole("button", { name: lang === "ko" ? "계획 확인하기" : /Check my plan/i }).click();
    await page.waitForURL(/\/intakes\/[0-9a-f-]{36}$/, { timeout: 60_000 });
    // 읽기가 끝나 결과가 자리 잡을 때까지(결과 아래의 「전체 자동 추천」 단추가 나온다 — 고칠 곳이 있는 판이라 「여행 등록」 대신 「재검증」이 있다)
    await page.getByRole("button", { name: lang === "ko" ? /전체 자동 추천/ : /Recommend all/i }).waitFor({ timeout: 60_000 });
    await page.waitForTimeout(1500);                                   // 지도 핀 · 시트 움직임이 멈추도록
    return { name: "3-results", clip: { x: 0, y: 0, width: WIDTH, height: HEIGHT }, viewportOnly: true };
  },
  /** 4. 채팅 — 등록된 여행의 채팅 탭에서 「하루 요약」을 눌러 답이 온 모습. mock 서버가 필요하다. */
  "4": async (page, lang, context) => {
    await mock(context.request, "/__test/reset");
    await mock(context.request, "/__test/scenario", { chat: "summary" });   // 「하루 요약」에 하루의 일정을 실제 서버가 쓰는 모양으로 답한다
    await page.setViewportSize({ width: WIDTH, height: HEIGHT });
    await page.goto(`${BASE}/trips/${TRIP_ID}`, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: lang === "ko" ? "채팅" : /Chat/i, exact: true }).click();
    const chat = page.locator("#trip-pane-chat");
    await chat.getByRole("button", { name: lang === "ko" ? "하루 요약" : /Day summary/i }).click();
    await chat.locator("article[data-role=assistant]").last().waitFor({ timeout: 30_000 });
    await page.waitForTimeout(800);
    await page.evaluate(() => { const card = document.querySelector("#trip-pane-chat"); if (card) window.scrollTo(0, Math.max(0, card.getBoundingClientRect().top + window.scrollY - 24)); });   // 채팅 카드의 머리가 위에 오도록
    return { name: "4-chat", clip: { x: 0, y: 0, width: WIDTH, height: HEIGHT }, viewportOnly: true };
  },
};

// ★이 PC 의 시험은 설치된 Chrome 을 쓴다(`PLAYWRIGHT_CHANNEL=chrome`). Playwright 가 받는 브라우저(chromium)는 이 버전용이 없어 「npx playwright install」을 요구한다 — 내려받지 않는다.
const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || "chrome" });
let made = 0;
for (const lang of languages) {
  for (const key of only) {
    if (!shots[key]) { console.log(`건너뜀: ${key}번은 이 스크립트에 없다`); continue; }
    if ((key === "3" || key === "4") && !MOCK) { console.log(`건너뜀: ${key}번은 mock 서버가 필요하다(--mock <주소>)`); continue; }
    const context = await browser.newContext({ viewport: { width: WIDTH, height: 844 }, deviceScaleFactor: SCALE, locale: lang === "ko" ? "ko-KR" : "en-US", isMobile: true, hasTouch: true });
    await context.addInitScript(([sKey, oKey, language, answers]) => {
      localStorage.setItem(sKey, JSON.stringify({ language, navigation: "fixed", theme: "green", skipAnimation: true }));
      localStorage.setItem(oKey, JSON.stringify({ read: true, agreed: true, complete: false, step: 0, answers }));
    }, [settingsKey, onboardingKey, lang, blankAnswers]);
    if (MOCK) await context.addCookies([{ name: SESSION_COOKIE, value: "known-session", url: MOCK }]);   // 돌아온 방문자 — mock 서버가 아는 세션
    const page = await context.newPage();
    try {
      const { name, clip, viewportOnly } = await shots[key](page, lang, context);
      await page.waitForTimeout(600);                                // 전환 효과가 끝나도록
      const file = path.join(OUT, `tripilot-guide-${lang}-${name}.jpg`);
      await mkdir(OUT, { recursive: true });
      await page.screenshot({ path: file, type: "jpeg", quality: 88, ...(viewportOnly ? {} : { clip, fullPage: true }) });
      console.log(`저장: ${path.relative(process.cwd(), file)}`);
      made += 1;
    } finally {
      await context.close();
    }
  }
}
await browser.close();
console.log(`끝 — ${made}장`);
