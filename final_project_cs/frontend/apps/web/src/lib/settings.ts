"use client";

import { useMemo, useSyncExternalStore } from "react";
import { languages, translator, type Language, type Translate } from "./i18n";
import { settingsStorageKey as storageKey, themes, type Theme } from "./theme";

export interface Settings {
  language: Language;
  theme: Theme;
  /**
   * `[2026-10-03 사용자 결정]` 메뉴의 「애니메이션 건너뛰기」: on = the plan check shows what the server sent at once, without the step-by-step
   * replay. It is the customer's own choice in the menu — the system's 「동작 줄이기」 no longer skips the steps (they are information, not motion).
   */
  skipAnimation: boolean;
  /**
   * `[2026-10-06 사용자 지시 — 첫 화면 · 확인 화면과 일관되게 전체를 모바일 기준으로, 메뉴에서 데스크탑을 고르면 그때 데스크탑 화면]` The registration, trip list, trip and my-page screens stand in the same
   * phone-sized frame as the intro and the plan check. On = those screens use the whole width of a wide window instead (the menu's 「데스크탑 화면으로 보기」).
   */
  desktopLayout: boolean;
}

// `[2026-10-03 사용자 결정]` 기본 언어는 한국어다 — 처음 여는 사람에게 한국어로 보인다(바꾸면 이 브라우저가 기억한다).
// `[2026-10-07 사용자 결정]` 「플로팅 버튼 사용」(여행 화면 하단 탭 ↔ 떠 있는 버튼)은 없앴다 — 새 여행 화면에는 하단 탭이 없다. 옛 버전이 저장한 `navigation` 은 읽지 않는다.
const defaults: Settings = { language: "ko", theme: "green", skipAnimation: false, desktopLayout: false };
const listeners = new Set<() => void>();
let current: Settings | null = null;

function read(): Settings {
  if (current) return current;
  current = defaults;
  try {
    const stored = JSON.parse(localStorage.getItem(storageKey) ?? "null") as Partial<Settings> | null;
    current = {
      language: languages.find(([value]) => value === stored?.language)?.[0] ?? defaults.language,
      theme: themes.find((value) => value === stored?.theme) ?? defaults.theme,
      skipAnimation: stored?.skipAnimation === true,
      desktopLayout: stored?.desktopLayout === true,
    };
  } catch {
    // Settings are a per-browser convenience; unreadable storage keeps the defaults.
  }
  return current;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function updateSettings(next: Partial<Settings>) {
  current = { ...read(), ...next };
  try { localStorage.setItem(storageKey, JSON.stringify(current)); }
  catch { /* The choice still applies to this page when storage is unavailable. */ }
  listeners.forEach((listener) => listener());
}

/** Server rendering and hydration use the defaults; the saved choice applies right after. */
export function useSettings(): Settings {
  return useSyncExternalStore(subscribe, read, () => defaults);
}

export function useT(): Translate {
  const { language } = useSettings();
  return useMemo(() => translator(language), [language]);
}
