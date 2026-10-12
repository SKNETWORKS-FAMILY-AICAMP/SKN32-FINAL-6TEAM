"use client";

import { useEffect, useSyncExternalStore } from "react";
import type { Language } from "@/lib/i18n";
import { openApi } from "@/lib/live/client";
import { buildTermsDocs, RETENTION, TERMS_DOCS, TERMS_VERSION, type Bilingual, type Retention, type TermsDoc } from "./terms-content";

/**
 * `[2026-10-07 사용자 결정 · cs 구축 세션 요청]` 약관 버전과 보관 기간 문장을 cs 프로젝트 서버에서 읽는다(`GET /v1/web/legal/retention`, 세션 없이 — 묻기만 해도 사용자가
 * 만들어지면 안 된다). 보관 기간은 관리자 화면에서 고칠 수 있고, 고치면 서버의 약관 버전이 `2026-10-07.1+ret{N}` 처럼 바뀐다 — 웹이 상수 버전으로 동의를 보내면
 * 409 `terms_version_changed` 가 나므로 버전도 서버 것을 쓴다.
 *   - 서버가 이 경로를 모르거나(옛 서버) 못 읽으면 웹에 실린 기본값(`TERMS_VERSION` · `RETENTION`)을 그대로 쓴다.
 *   - 서버 칸 이름 → 약관 본문의 자리: 아래 `SLOT`. 모르는 칸은 버린다(새 서버가 칸을 더 줄 수 있다). 문장이 빈 칸은 기본값을 둔다.
 */
const SLOT = {
  member_idle_days: "memberData",
  case_follows_trip: "caseRecords",
  consent_days: "consentRecords",
  location_points_days: "locationPoints",
  location_proof_months: "locationFactLog",
} as const satisfies Record<string, keyof typeof RETENTION>;

export interface LiveTerms {
  version: string;
  docs: readonly TermsDoc[];
  /** True = read from the server; false = the defaults this page carries. */
  fromServer: boolean;
}

const DEFAULTS: LiveTerms = { version: TERMS_VERSION, docs: TERMS_DOCS, fromServer: false };
let live: LiveTerms = DEFAULTS;
let loading: Promise<LiveTerms> | null = null;
let tried = false;
const listeners = new Set<() => void>();

interface WireCell { key?: unknown; text_ko?: unknown; text_en?: unknown }
interface Wire { terms_version?: unknown; cells?: unknown }

const text = (value: unknown): string | null => typeof value === "string" && value.trim() ? value.trim() : null;

/** What the server said, read defensively. Null = nothing usable (no version) — the defaults stay. */
export function readLiveTerms(wire: Wire | null | undefined): LiveTerms | null {
  const version = text(wire?.terms_version);
  if (!version) return null;
  const retention: Record<keyof typeof RETENTION, Bilingual> = { ...RETENTION };
  for (const raw of Array.isArray(wire?.cells) ? wire.cells as WireCell[] : []) {
    const slot = typeof raw?.key === "string" ? (SLOT as Record<string, keyof typeof RETENTION>)[raw.key] : undefined;
    const ko = text(raw?.text_ko), en = text(raw?.text_en);
    if (slot && ko && en) retention[slot] = [ko, en];
  }
  return { version, docs: buildTermsDocs(retention as Retention), fromServer: true };
}

function set(next: LiveTerms) {
  if (next.version === live.version && next.fromServer === live.fromServer && JSON.stringify(next.docs) === JSON.stringify(live.docs)) return;
  live = next;
  listeners.forEach((listener) => listener());
}

/** The terms in force now (server's when read, else the defaults). */
export function liveTerms(): LiveTerms { return live; }
/** The terms version consents are bound to and sent with. */
export function termsVersion(): string { return live.version; }
/** The five documents in the order of the consent screen. */
export function termsDocs(): readonly TermsDoc[] { return live.docs; }

export function subscribeTerms(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => { listeners.delete(onChange); };
}

/**
 * Read the server's terms once (concurrent callers share the request). `force` reads again — after the server said the version moved on (409).
 * Never throws: a failure keeps what is there.
 */
export function loadLiveTerms(language: Language, force = false): Promise<LiveTerms> {
  if (tried && !force) return loading ?? Promise.resolve(live);
  tried = true;
  loading = (async () => {
    try {
      const read = readLiveTerms(await openApi<Wire>("/v1/web/legal/retention", language));
      if (read) set(read);
    } catch { /* 옛 서버(404) · 연결 실패: 웹에 실린 기본값 그대로 */ }
    return live;
  })().finally(() => { loading = null; });
  return loading;
}

/** For screens: the terms in force, read from the server on first use. */
export function useLiveTerms(language: Language): LiveTerms {
  const value = useSyncExternalStore(subscribeTerms, liveTerms, () => DEFAULTS);
  useEffect(() => { void loadLiveTerms(language); }, [language]);
  return value;
}

/** Tests only: forget what was read. */
export function resetLiveTerms() {
  live = DEFAULTS;
  loading = null;
  tried = false;
  listeners.forEach((listener) => listener());
}
