import { CONSENT_CODES, type ConsentCode } from "@/features/consent/consent-model";
import type { Language } from "../i18n";
import { api, LiveError } from "./client";

/**
 * `[2026-10-05 사용자 지시]` 약관 동의의 서버 기록(`GET/POST /v1/web/consents`, 계약: `wiki/records/plans/2026-10-05_동의기록_위치수집_백엔드_요청.md`).
 * 서버가 정본이다: 누가 어떤 약관 버전의 어떤 항목에 언제 동의했는지(철회 포함)를 추가만 하는 표에 남기고, 필수 동의가 없으면 다른 호출을 403 `consent_required` 로 막는다.
 * 여기는 그 호출을 읽고 보내는 곳이다 - 동의 화면과 이 브라우저의 사본은 `features/consent/`.
 */
export interface ServerConsentItem { code: ConsentCode; agreed: boolean; version: string; agreedAt: string | null }
export interface ServerConsents { currentVersion: string; required: ConsentCode[]; items: ServerConsentItem[]; ok: boolean }

interface Wire {
  current_version?: unknown;
  required?: unknown;
  items?: unknown;
  ok?: unknown;
}

const isCode = (value: unknown): value is ConsentCode => typeof value === "string" && (CONSENT_CODES as readonly string[]).includes(value);

/** What the server said, read defensively: an unknown code is dropped (a newer server may have more), `ok` is true only when it says so. */
export function readServerConsents(wire: Wire | null | undefined): ServerConsents {
  const items: ServerConsentItem[] = [];
  for (const raw of Array.isArray(wire?.items) ? wire.items : []) {
    const row = raw as { code?: unknown; agreed?: unknown; version?: unknown; agreed_at?: unknown };
    if (!isCode(row.code)) continue;
    items.push({ code: row.code, agreed: row.agreed === true, version: typeof row.version === "string" ? row.version : "", agreedAt: typeof row.agreed_at === "string" ? row.agreed_at : null });
  }
  return {
    currentVersion: typeof wire?.current_version === "string" ? wire.current_version : "",
    required: (Array.isArray(wire?.required) ? wire.required : []).filter(isCode),
    items,
    ok: wire?.ok === true,
  };
}

export async function getServerConsents(language: Language): Promise<ServerConsents> {
  return readServerConsents(await api<Wire>("/v1/web/consents", language));
}

/** One item as it is sent: the choice and the fingerprint of the Korean text the customer was shown (`text_sha256`). */
export interface ConsentChoice { code: ConsentCode; agreed: boolean; textSha256: string }

/** Record the customer's choices for the terms version this page carries. 409 `terms_version_changed` = the server moved on to a newer version. */
export async function postServerConsents(version: string, choices: ConsentChoice[], language: Language): Promise<ServerConsents> {
  const body = { version, items: choices.map((choice) => ({ code: choice.code, agreed: choice.agreed, text_sha256: choice.textSha256 })) };
  return readServerConsents(await api<Wire>("/v1/web/consents", language, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }));
}

/** An older server without the consent record (404/405): the choices then live in this browser only. */
export function isConsentsUnsupported(error: unknown): boolean {
  return error instanceof LiveError && ["not_found", "method_not_allowed", "HTTP_404", "HTTP_405"].includes(error.code);
}

/** The server refuses a call until the required consents are on record (403 `consent_required`). */
export function isConsentRequired(error: unknown): boolean {
  return error instanceof LiveError && error.code === "consent_required";
}

/** The server's current terms version is not the one this page carries (409): the page is out of date. */
export function isTermsVersionChanged(error: unknown): boolean {
  return error instanceof LiveError && error.code === "terms_version_changed";
}
