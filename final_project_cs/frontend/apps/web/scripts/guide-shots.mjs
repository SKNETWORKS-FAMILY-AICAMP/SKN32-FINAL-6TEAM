// 소개 화면의 「이용 방법」 그림(public/images/tripilot-guide-<언어>-<번호>-<이름>.jpg)을 실제 화면에서 다시 찍는다.
//
//   왜 있나(2026-10-04 사용자 질문 「패치할 때마다 다시 캡처 안 해도 되잖아」): 화면을 소개에 그대로 끼우면 두 화면(취향·계획 입력)이
//   서버 호출·사람 확인·방문자의 저장 상태를 안고 있어 부작용이 생긴다. 그래서 그림으로 두되, 손으로 찍지 않고 이 스크립트 한 줄로 다시 찍는다.
//
//   쓰는 법(웹 개발 서버가 떠 있어야 한다 — 기본 http://127.0.0.1:3100):
//     node scripts/guide-shots.mjs                  # 찍을 수 있는 것 전부(ko·en)
//     node scripts/guide-shots.mjs --only 1,2       # 번호로 고르기
//     node scripts/guide-shots.mjs --lang ko        # 언어로 고르기
//     GUIDE_BASE=http://127.0.0.1:3100 node scripts/guide-shots.mjs
//   번호: 1 취향 · 2 계획 입력 · 3 점검 결과(서버 필요) · 4 채팅(서버·등록된 여행 필요)
//
//   덮어쓰기 전에 옛 그림을 `<저장소>/frontend/_backup/<날짜>_이용방법그림_옛판/` 에 복사해 두는 것은 사람이 한다(전역 규칙).
//   ★이 스크립트는 서버에 여행을 만들지 않는다. 3·4번이 서버를 쓰는 부분은 아래 각 함수 주석을 본다.
import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const BASE = process.env.GUIDE_BASE ?? "http://127.0.0.1:3100";
const HERE = path.dirname(fileURLToPath(import.meta.url));
const WIDTH = 390, HEIGHT = 560, SCALE = 2;     // 780 × 1120 — 소개 화면의 그림 칸(width=780 height=1120)과 같다

const argv = process.argv.slice(2);
const option = (name) => { const at = argv.indexOf(`--${name}`); return at >= 0 ? argv[at + 1] : undefined; };
// --out <폴더> (또는 GUIDE_OUT): 먼저 다른 폴더에 찍어 눈으로 보고 싶을 때. 없으면 소개 화면이 쓰는 public/images 에 바로 쓴다.
const OUT = option("out") ? path.resolve(option("out")) : process.env.GUIDE_OUT ?? path.resolve(HERE, "..", "public", "images");
const only = (option("only") ?? "1,2").split(",").map((value) => value.trim());
const languages = (option("lang") ?? "ko,en").split(",").map((value) => value.trim());

const settingsKey = "tripilot.web.settings.v1";
const onboardingKey = "tripilot.web.onboarding.v1";
const blankAnswers = { theme: "", party: "", partyOther: "", priority: [], details: { food: [], activity: [], mobility: [] }, indoorDining: "", indoorActivity: "", onDisruption: "", pace: "", skipped: [] };

const shots = {
  /** 1. 취향 — 첫 질문에서 「맛집 탐방」을 골라 둔 모습. 약관에 동의한 상태로 시작해 취향 카드를 연다. 서버를 쓰지 않는다. */
  "1": async (page, lang) => {
    await page.goto(`${BASE}/start`, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: lang === "ko" ? /여행 취향 알아보기/ : /Your travel preferences/ }).click();
    await page.getByRole("button", { name: lang === "ko" ? "맛집 탐방" : "Food", exact: true }).click();
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
};

// ★이 PC 의 시험은 설치된 Chrome 을 쓴다(`PLAYWRIGHT_CHANNEL=chrome`). Playwright 가 받는 브라우저(chromium)는 이 버전용이 없어 「npx playwright install」을 요구한다 — 내려받지 않는다.
const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || "chrome" });
let made = 0;
for (const lang of languages) {
  for (const key of only) {
    if (!shots[key]) { console.log(`건너뜀: ${key}번은 아직 이 스크립트에 없다`); continue; }
    const context = await browser.newContext({ viewport: { width: WIDTH, height: 844 }, deviceScaleFactor: SCALE, locale: lang === "ko" ? "ko-KR" : "en-US", isMobile: true, hasTouch: true });
    await context.addInitScript(([sKey, oKey, language, answers]) => {
      localStorage.setItem(sKey, JSON.stringify({ language, navigation: "fixed", theme: "green", skipAnimation: true }));
      localStorage.setItem(oKey, JSON.stringify({ read: true, agreed: true, complete: false, step: 0, answers }));
    }, [settingsKey, onboardingKey, lang, blankAnswers]);
    const page = await context.newPage();
    try {
      const { name, clip } = await shots[key](page, lang);
      await page.waitForTimeout(600);                                // 전환 효과가 끝나도록
      const file = path.join(OUT, `tripilot-guide-${lang}-${name}.jpg`);
      await mkdir(OUT, { recursive: true });
      await page.screenshot({ path: file, type: "jpeg", quality: 88, clip, fullPage: true });
      console.log(`저장: ${path.relative(process.cwd(), file)}`);
      made += 1;
    } finally {
      await context.close();
    }
  }
}
await browser.close();
console.log(`끝 — ${made}장`);
