import { translator, type Language, type Translate } from "../i18n";

/** A refusal from the live server — its own code (`stale_revision`, `intake_incomplete` …) and body. */
export class LiveError extends Error {
  constructor(public readonly code: string, message: string, public readonly detail?: unknown) {
    super(message);
    this.name = "LiveError";
  }
}

/**
 * Live connection to the triPilot server (`/v1/web/*`).
 *
 * The browser never holds a server scope key. It holds one user key (`X-User-Key`, `acop_u_…`) that
 * opens only this user's own trips. The key lives in localStorage and is shown once so the user can
 * keep a copy; if it leaks, rotating it on the server cuts the old one off.
 */
export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8042").replace(/\/$/, "");
const KEY_STORAGE = "tripilot.web.user-key.v1";
/** Set when a key was just issued: the screen shows it once so the customer can keep a copy (D-020, D-021 §4). */
const NOTICE_STORAGE = "tripilot.web.user-key.notice.v1";
/** Fired on this page whenever the key or its notice changes, so the screen re-reads them. */
export const KEY_CHANGED_EVENT = "tripilot:key-changed";

let pendingKey: Promise<string> | null = null;

function storedKey(): string | null {
  try { return window.localStorage.getItem(KEY_STORAGE); }
  catch { return null; }
}

function storeKey(key: string) {
  try { window.localStorage.setItem(KEY_STORAGE, key); }
  catch { /* private window: the key lives only for this page */ }
  announceKeyChange();
}

function announceKeyChange() {
  try { window.dispatchEvent(new Event(KEY_CHANGED_EVENT)); } catch { /* not in a browser */ }
}

/** The server's own sentence about the new key (`notice`), kept until the customer says they saved it. */
function setKeyNotice(notice: string | null) {
  try { window.localStorage.setItem(NOTICE_STORAGE, JSON.stringify({ notice })); } catch { /* ignore */ }
  announceKeyChange();
}

/** A key was issued or rotated and the customer has not yet said they kept a copy. `notice` is the server's sentence (may be absent). */
export function pendingKeyNotice(): { notice: string | null } | null {
  try {
    const raw = window.localStorage.getItem(NOTICE_STORAGE);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { notice?: unknown };
    return { notice: typeof parsed.notice === "string" ? parsed.notice : null };
  } catch { return null; }
}

export function dismissKeyNotice() {
  try { window.localStorage.removeItem(NOTICE_STORAGE); } catch { /* ignore */ }
  announceKeyChange();
}

/** The user key, issued on first use. Concurrent first calls share one issue request. */
export async function userKey(language: Language): Promise<string> {
  const existing = storedKey();
  if (existing) return existing;
  return issueKey(language);
}

/**
 * Issue a new key now. `humanToken` is the Turnstile token when the human check is on — key issuance is where a
 * sign-up flood comes in, so the server checks it there (`{"turnstile_token"}`, D-021 · abuse plan 2026-09-28).
 */
export async function issueKey(language: Language, humanToken?: string | null): Promise<string> {
  pendingKey ??= (async () => {
    // ★Keep `method` inside the call — the server contract test (tests/contract/test_web_client_contract.py) reads
    //   it from there and counts a call it cannot read as GET.
    const response = await send(`${API_BASE}/v1/web/session`, {
      method: "POST",
      ...(humanToken ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify({ turnstile_token: humanToken }) } : {}),
    }, language);
    const body = await response.json() as { user_key: string; notice?: string };
    storeKey(body.user_key);
    setKeyNotice(body.notice ?? null);
    return body.user_key;
  })().finally(() => { pendingKey = null; });
  return pendingKey;
}

export function currentKey(): string | null {
  return typeof window === "undefined" ? null : storedKey();
}

/**
 * ★`[2026-10-01]` A call that gets no answer must end. With no limit, a server stuck behind a stopped database left
 * the 「Open」 button locked for good (its request never returned, so the screen kept waiting). Most calls answer in
 * seconds; the few that read many places or wake the chat model, or carry files, get longer.
 */
const ANSWER_WITHIN_MS = 60_000;
const SLOW_ANSWER_WITHIN_MS = 180_000;
const SLOW_CALL = /\/(plan|confirm|messages|trip-intakes)$/;

export function answerWithin(url: string): number {
  try { return SLOW_CALL.test(new URL(url).pathname) ? SLOW_ANSWER_WITHIN_MS : ANSWER_WITHIN_MS; }
  catch { return ANSWER_WITHIN_MS; }
}

async function send(url: string, init: RequestInit, language: Language): Promise<Response> {
  const t = translator(language);
  let response: Response;
  const limit = AbortSignal.timeout(answerWithin(url));
  try { response = await fetch(url, { ...init, signal: init.signal ? AbortSignal.any([init.signal, limit]) : limit }); }
  catch {
    if (limit.aborted && !init.signal?.aborted) throw new LiveError("timeout", t("서버가 응답하지 않아요. 잠시 뒤 다시 시도해 주세요.", "The server is not answering. Please try again shortly."));
    throw new LiveError("network", t("서버에 연결하지 못했어요. 잠시 뒤 다시 시도해 주세요.", "Could not reach the server. Please try again shortly."));
  }
  if (response.ok) return response;
  let code = `HTTP_${response.status}`;
  let message = t(`요청을 처리하지 못했어요 (${response.status}).`, `The request failed (${response.status}).`);
  let detail: unknown;
  try {
    const body = await response.json() as { error?: { code?: string; message?: string } & Record<string, unknown> };
    if (body.error?.code) code = body.error.code;
    if (body.error?.message) message = body.error.message;
    detail = body.error;
  } catch { /* not JSON */ }
  // ★A limit says when it opens again (`Retry-After`, or `retry_after_seconds` in the body) — say it, so the
  //   customer is not left guessing whether to press again.
  if (["usage_limit", "service_daily_cap", "too_many_sessions"].includes(code)) {
    const seconds = Number((detail as { retry_after_seconds?: unknown } | undefined)?.retry_after_seconds ?? response.headers.get("Retry-After"));
    if (Number.isFinite(seconds) && seconds > 0) message = `${message} ${waitText(seconds, t)}`;
  }
  throw new LiveError(code, message, detail);
}

/** 「3시간 20분 뒤에 다시 할 수 있어요」 — whole minutes, rounded up. */
export function waitText(seconds: number, t: Translate): string {
  const minutes = Math.max(1, Math.ceil(seconds / 60));
  const hours = Math.floor(minutes / 60), rest = minutes % 60;
  const ko = hours ? `${hours}시간${rest ? ` ${rest}분` : ""}` : `${rest}분`;
  const en = hours ? `${hours} h${rest ? ` ${rest} min` : ""}` : `${rest} min`;
  return t(`(${ko} 뒤에 다시 할 수 있어요.)`, `(You can try again in ${en}.)`);
}

/**
 * A request with the user key.
 *
 * A 401 means the stored key was rotated or removed. We do NOT quietly issue a new key and retry: a new
 * key is a new user, and the old trips would silently disappear from view. The stored key is dropped and
 * the user is told; the next action starts with a fresh key.
 */
export async function api<T>(path: string, language: Language, init: RequestInit = {}): Promise<T> {
  const t = translator(language);
  const key = await userKey(language);
  try {
    const response = await send(`${API_BASE}${path}`, { ...init, headers: { ...(init.headers ?? {}), "X-User-Key": key } }, language);
    return await response.json() as T;
  } catch (error) {
    if (!(error instanceof LiveError) || error.code !== "unauthenticated") throw error;
    try { window.localStorage.removeItem(KEY_STORAGE); } catch { /* ignore */ }
    throw new LiveError("key_rejected", t("저장된 사용자 키가 더 이상 맞지 않아요. 다음 요청부터 새 키로 시작해요 — 이전 여행은 따로 보관한 키로만 열 수 있어요.", "Your saved user key is no longer valid. The next request starts with a new key — earlier trips open only with the key you kept."));
  }
}

/**
 * Use a key the customer already has (another device, or one they kept). It is checked against the server first —
 * a key the server does not know is refused and the stored one is left as it was.
 */
export async function adoptKey(raw: string, language: Language): Promise<void> {
  const key = raw.trim();
  if (!key) throw new LiveError("empty_key", translator(language)("키를 입력해 주세요.", "Enter a key."));
  await send(`${API_BASE}/v1/web/trips`, { headers: { "X-User-Key": key } }, language);
  storeKey(key);
  dismissKeyNotice();
}

/**
 * Ask the server for a new key (`POST /v1/web/session/rotate`). ★The old key stops working at once, so the new one is
 * stored and shown immediately for the customer to keep.
 */
export async function rotateKey(language: Language): Promise<void> {
  const body = await api<{ user_key: string; notice?: string }>("/v1/web/session/rotate", language, { method: "POST" });
  storeKey(body.user_key);
  setKeyNotice(body.notice ?? null);
}
