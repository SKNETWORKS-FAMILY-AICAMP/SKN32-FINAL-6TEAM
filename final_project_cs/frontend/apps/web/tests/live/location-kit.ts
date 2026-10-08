import type { BrowserContext, Page } from "@playwright/test";
import { TERMS_VERSION } from "../../src/features/consent/terms-content";
import { agree, APP, CONSENT_STORAGE, start } from "./helpers";

/**
 * `[2026-10-05]` 「내 위치」 시험이 함께 쓰는 도구 — 위치 동의를 정해 시작하기 · 브라우저 위치 흉내 · 위치를 묻는 호출 세기 · 페이지 숨기기.
 * mock 서버 시험(화면 반응)용이다. 위치 값은 시험용 좌표이고 어디에도 기록하지 않는다.
 */

/**
 * 돌아온 고객으로 시작한다(세션 쿠키 · 한국어 · 필수 약관 동의) — 위치 동의는 `location`.
 * ★`agree` 를 `start` 보다 먼저 건다: 동의 사본은 「아직 없을 때만」 심기므로 먼저 심은 것이 남는다(`start` 는 위치 동의 없이 심는다).
 */
export async function startWithLocationConsent(page: Page, location: boolean) {
  await agree(page, { location });
  await start(page);
}

/** 이 페이지가 열린 뒤 위치 동의를 바꾼다(마이페이지에서 끈 것처럼) — 다른 탭에서 바뀐 것과 같은 `storage` 알림으로 화면이 다시 읽는다. */
export async function changeLocationConsent(page: Page, location: boolean) {
  await page.evaluate(([key, version, agreed]) => {
    localStorage.setItem(key, JSON.stringify({ version, items: { service_terms: true, privacy: true, sensitive: false, location: agreed, alert_channel: false }, at: new Date().toISOString(), synced: true }));
    window.dispatchEvent(new StorageEvent("storage", { key }));
  }, [CONSENT_STORAGE, TERMS_VERSION, location] as const);
}

/** 브라우저가 위치를 알려 주게 하고(권한 허용) 그 위치를 정한다. */
export async function allowLocation(context: BrowserContext, at: { latitude: number; longitude: number; accuracy?: number }) {
  await context.grantPermissions(["geolocation"], { origin: APP });
  await context.setGeolocation({ accuracy: 20, ...at });
}

/** 페이지가 브라우저에 위치를 물은 횟수(`watchPosition` · `getCurrentPosition`)를 센다 — 페이지를 열기 전에 건다. */
export async function countLocationAsks(page: Page) {
  await page.addInitScript(() => {
    const counted = window as Window & { __locationAsks?: number };
    counted.__locationAsks = 0;
    const geo = navigator.geolocation;
    const watch = geo.watchPosition.bind(geo), current = geo.getCurrentPosition.bind(geo);
    geo.watchPosition = (...args: Parameters<Geolocation["watchPosition"]>) => { counted.__locationAsks = (counted.__locationAsks ?? 0) + 1; return watch(...args); };
    geo.getCurrentPosition = (...args: Parameters<Geolocation["getCurrentPosition"]>) => { counted.__locationAsks = (counted.__locationAsks ?? 0) + 1; return current(...args); };
  });
}

export const locationAsks = (page: Page) => page.evaluate(() => (window as Window & { __locationAsks?: number }).__locationAsks ?? 0);

/** 다른 탭으로 가거나 화면을 끈 것처럼 페이지를 숨긴다(`hidden: false` 면 다시 보인다). 화면은 숨겨질 때 모아 둔 위치 점을 서버로 보낸다. */
export async function setPageHidden(page: Page, hidden: boolean) {
  await page.evaluate((value) => {
    Object.defineProperty(document, "visibilityState", { configurable: true, get: () => (value ? "hidden" : "visible") });
    Object.defineProperty(document, "hidden", { configurable: true, get: () => value });
    document.dispatchEvent(new Event("visibilitychange"));
  }, hidden);
}

/** 북쪽으로 `metres` 만큼 옮긴 위도(위도 1도 ≈ 111 195 m). */
export const north = (latitude: number, metres: number) => latitude + metres / 111_195;
