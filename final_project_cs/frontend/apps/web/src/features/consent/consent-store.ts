"use client";

import { useSyncExternalStore } from "react";
import { CONSENT_CODES, noConsents, type ConsentCode, type ConsentMap } from "./consent-model";
import { TERMS_VERSION } from "./terms-content";

/**
 * `[2026-10-05 사용자 지시]` 이 브라우저가 기억하는 동의. ★정본은 서버의 동의 기록(`/v1/web/consents`)이다 - 여기는 화면이 곧바로 알아야 할 때(지도에 내 위치를
 * 그릴지 · 약관 화면을 다시 보여 줄지)를 위한 사본이고, 서버 기록과 어긋나면 서버가 이긴다(`replaceConsents`).
 *
 * - 동의는 **약관 버전**에 묶인다. 저장된 버전이 지금 버전(`TERMS_VERSION`)과 다르면 아무것도 동의하지 않은 것으로 읽는다(다시 동의 받음).
 * - 브라우저 저장소를 못 쓰면(사생활 보호 창 등) 이 페이지가 열려 있는 동안만 기억한다.
 */
const KEY = "tripilot.web.consent.v1";
interface Stored {
  version: string;
  items: ConsentMap;
  at: string | null;
  /** The server has this choice on record. False = it still has to be sent (the customer chose offline, or before any session). */
  synced: boolean;
}

let memory: Stored | null = null;
let loaded = false;
const listeners = new Set<() => void>();

function load(): Stored | null {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<Stored>;
    if (!parsed || typeof parsed.version !== "string" || typeof parsed.items !== "object" || parsed.items === null) return null;
    const items = noConsents();
    for (const code of CONSENT_CODES) items[code] = (parsed.items as Partial<ConsentMap>)[code] === true;
    return { version: parsed.version, items, at: typeof parsed.at === "string" ? parsed.at : null, synced: parsed.synced === true };
  } catch {
    return null;
  }
}

function current(): Stored | null {
  if (!loaded && typeof window !== "undefined") { memory = load(); loaded = true; }
  return memory;
}

function emit() { listeners.forEach((listener) => listener()); }

/** 지금 버전에 대한 동의. 저장된 것이 없거나 옛 버전이면 모두 false. */
export function readConsents(): ConsentMap {
  const stored = current();
  return stored && stored.version === TERMS_VERSION ? { ...stored.items } : noConsents();
}

/** 동의 시각(ISO). 없으면 null. */
export function consentedAt(): string | null {
  const stored = current();
  return stored && stored.version === TERMS_VERSION ? stored.at : null;
}

/** 서버에 이 동의가 기록돼 있나. 저장된 것이 없거나 옛 버전이면 false. */
export function consentsSynced(): boolean {
  const stored = current();
  return Boolean(stored && stored.version === TERMS_VERSION && stored.synced);
}

/** 서버에 기록됐다고 표시한다(보낸 뒤, 또는 서버가 이 동의를 이미 갖고 있을 때). */
export function markConsentsSynced(): void {
  const stored = current();
  if (!stored || stored.version !== TERMS_VERSION || stored.synced) return;
  replaceConsents(stored.items, stored.at, true);
}

/** 동의를 통째로 바꾼다(약관 화면에서 저장했거나, 서버 기록을 읽어 와서 맞출 때). `synced` = 서버가 이미 아는 값인가(서버에서 읽어 온 것이면 true). */
export function replaceConsents(items: ConsentMap, at: string | null = new Date().toISOString(), synced = false): void {
  memory = { version: TERMS_VERSION, items: { ...items }, at, synced };
  loaded = true;
  try { window.localStorage.setItem(KEY, JSON.stringify(memory)); } catch { /* 사생활 보호 창: 이 페이지가 열려 있는 동안만 */ }
  emit();
}

/** 항목 하나만 바꾼다(마이페이지에서 선택 동의를 켜고 끌 때). */
export function setConsent(code: ConsentCode, agreed: boolean): void {
  replaceConsents({ ...readConsents(), [code]: agreed }, new Date().toISOString());
}

/** 시험용: 저장된 동의를 모두 잊는다. */
export function forgetConsents(): void {
  memory = null;
  loaded = true;
  try { window.localStorage.removeItem(KEY); } catch { /* 무시 */ }
  emit();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  const onStorage = (event: StorageEvent) => { if (event.key === KEY) { loaded = false; emit(); } };
  if (typeof window !== "undefined") window.addEventListener("storage", onStorage);
  return () => { listeners.delete(listener); if (typeof window !== "undefined") window.removeEventListener("storage", onStorage); };
}

/**
 * 이 항목에 동의했나. ★서버 렌더와 첫 화면은 항상 false 로 시작한다(저장소는 화면이 붙은 뒤에야 읽힌다) - 동의에 기대는 화면은 동의했다고 가정하고 그리지 않는다.
 */
export function useConsent(code: ConsentCode): boolean {
  return useSyncExternalStore(subscribe, () => readConsents()[code], () => false);
}

/** 필수 동의가 모두 있나(앱을 쓸 수 있나). 서버 렌더에서는 false. */
export function useRequiredConsents(): boolean {
  return useSyncExternalStore(subscribe, () => readConsents().service_terms && readConsents().privacy, () => false);
}
