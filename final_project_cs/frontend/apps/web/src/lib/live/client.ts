import { translator, type Language, type Translate } from "../i18n";
import { beginWait, CALL_STEPS } from "./waiting";

/** A refusal from the live server — its own code (`stale_revision`, `intake_incomplete` …) and body. */
export class LiveError extends Error {
  /** `[2026-10-05]` `status` = the HTTP status of the refusal (absent when there was no answer: offline, timed out). */
  constructor(public readonly code: string, message: string, public readonly detail?: unknown, public readonly status?: number) {
    super(message);
    this.name = "LiveError";
  }
}

/**
 * Live connection to the triPilot server (`/v1/web/*`).
 *
 * ★`[2026-10-04 사용자 결정 · 서버 D-CS-011]` The browser no longer holds a key. The server gives a session cookie (HttpOnly — no script of
 *   this page can read it), and every call carries it (`credentials: "include"`). A write also carries `X-CSRF-Token`, the token the
 *   server gave with the session; it is kept in memory only. The old `X-User-Key` header is for agents (MCP) and for a browser that still
 *   holds one: such a browser moves to a session once (`POST /v1/web/auth/adopt`) and forgets the key.
 * ★Never send the cookie and `X-User-Key` in one request — the server refuses it (`400 ambiguous_credentials`).
 */
export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8042").replace(/\/$/, "");

/** What an older version of this page kept in the browser; read only to move it to a session, then removed. */
const LEGACY_KEY_STORAGE = "tripilot.web.user-key.v1";
const LEGACY_NOTICE_STORAGE = "tripilot.web.user-key.notice.v1";

export type SessionKind = "guest" | "member";

/** The session the server gave this browser. `csrf` is memory-only. */
export interface WebSession {
  kind: SessionKind;
  csrf: string;
  /** Guests only: hours without use after which the session (and its trips) go away. */
  guestIdleHours: number | null;
  idleExpiresAt: string | null;
  absoluteExpiresAt: string | null;
}

/** Fired on this page whenever the session is made, ended or changes, so the screen re-reads it. */
export const SESSION_CHANGED_EVENT = "tripilot:session-changed";
/**
 * `[2026-10-05]` The server refused a call because the required consents are not on record (403 `consent_required`): tells the app (`ConsentGate`), which checks the
 * record again and, if the customer has not consented to the current terms, brings them to the terms screen.
 */
export const CONSENT_REQUIRED_EVENT = "tripilot:consent-required";

/** `probed`: the server was asked once. `failed`: it could not be asked (the screen says so instead of waiting for ever). */
export interface SessionSnapshot { probed: boolean; failed: boolean; session: WebSession | null }

let snapshot: SessionSnapshot = { probed: false, failed: false, session: null };

function setSnapshot(next: SessionSnapshot) {
  snapshot = next;
  try { window.dispatchEvent(new Event(SESSION_CHANGED_EVENT)); } catch { /* not in a browser */ }
}

/** The same object until something changes — what `useSyncExternalStore` needs. */
export function sessionSnapshot(): SessionSnapshot {
  return snapshot;
}

export function subscribeSession(onChange: () => void): () => void {
  window.addEventListener(SESSION_CHANGED_EVENT, onChange);
  return () => window.removeEventListener(SESSION_CHANGED_EVENT, onChange);
}

/** For tests: forget what this page knows about the session (module state outlives a test otherwise). Not used by the app. */
export function resetSessionState() {
  snapshot = { probed: false, failed: false, session: null };
  probing = null;
  creating = null;
}

/** The session this page knows right now (memory only — it does not ask the server). */
export function currentSession(): WebSession | null {
  return snapshot.session;
}

const text = (value: unknown): string | null => (typeof value === "string" && value ? value : null);

/** `{kind, csrf_token, guest_idle_hours?, idle_expires_at, absolute_expires_at}` → a session; null when the body is not one. */
export function sessionOf(body: unknown): WebSession | null {
  const entry = (body ?? {}) as Record<string, unknown>;
  const csrf = text(entry.csrf_token);
  const kind = entry.kind === "member" ? "member" : entry.kind === "guest" ? "guest" : null;
  if (!csrf || !kind) return null;
  const hours = Number(entry.guest_idle_hours);
  return {
    kind, csrf, guestIdleHours: kind === "guest" && Number.isFinite(hours) && hours > 0 ? hours : null,
    idleExpiresAt: text(entry.idle_expires_at), absoluteExpiresAt: text(entry.absolute_expires_at),
  };
}

/** Take the session an answer carried (a sign-in with `session: "cookie"`). */
export function takeSession(session: WebSession) {
  setSnapshot({ probed: true, failed: false, session });
}

function legacyKey(): string | null {
  try { return window.localStorage.getItem(LEGACY_KEY_STORAGE); }
  catch { return null; }
}

function forgetLegacyKey() {
  try { window.localStorage.removeItem(LEGACY_KEY_STORAGE); window.localStorage.removeItem(LEGACY_NOTICE_STORAGE); }
  catch { /* private window: nothing was kept */ }
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

/** Calls that are slow ON PURPOSE and not something the customer waits for (the model is warmed up in the background): they are not counted as a slow server. */
const BACKGROUND_CALL = /\/warmup$/;

async function send(url: string, init: RequestInit, language: Language): Promise<Response> {
  const t = translator(language);
  let response: Response;
  const limit = AbortSignal.timeout(answerWithin(url));
  // ★`[2026-10-06 사용자 지적]` A call that has not answered for a while is counted (`waiting.ts`), so the screen says the server is slow instead of staying silent.
  const wait = BACKGROUND_CALL.test(safePath(url)) ? null : beginWait(CALL_STEPS);
  try {
    try { response = await fetch(url, { ...init, signal: init.signal ? AbortSignal.any([init.signal, limit]) : limit }); }
    catch {
      if (limit.aborted && !init.signal?.aborted) throw new LiveError("timeout", t("서버가 응답하지 않아요. 잠시 뒤 다시 시도해 주세요.", "The server is not answering. Please try again shortly."));
      throw new LiveError("network", t("서버에 연결하지 못했어요. 잠시 뒤 다시 시도해 주세요.", "Could not reach the server. Please try again shortly."));
    }
    if (response.ok) return response;
    throw await refusal(response, language);
  } finally { wait?.end(); }
}

function safePath(url: string): string {
  try { return new URL(url).pathname; } catch { return url; }
}

/** A non-2xx answer → the server's own code and sentence (`{"error": {...}}`), with when a limit opens again. */
export async function refusal(response: Response, language: Language): Promise<LiveError> {
  const t = translator(language);
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
  return new LiveError(code, message, detail, response.status);
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
 * `[2026-10-04]` A guest may make one trip, starting within a year and lasting at most seven days; the server refuses more with
 * `guest_trip_limit` / `guest_trip_too_far` / `guest_trip_too_long` and `login_required: true`. The screen then says logging in lifts it.
 */
export function loginRequired(error: unknown): boolean {
  if (!(error instanceof LiveError)) return false;
  const detail = error.detail as { login_required?: unknown } | undefined;
  return detail?.login_required === true || error.code.startsWith("guest_");
}

/** The request as it must go with the session: the cookie always, and on a write the token that ties it to this session. */
function withSession(init: RequestInit, session: WebSession | null): RequestInit {
  const method = (init.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = { ...(init.headers as Record<string, string> | undefined) };
  if (session && !["GET", "HEAD", "OPTIONS"].includes(method)) headers["X-CSRF-Token"] = session.csrf;
  return { ...init, headers, credentials: "include" };
}

/**
 * A key an older version of this page kept is moved to a session, once: `POST /v1/web/auth/adopt` with the key alone (the server refuses a
 * request that carries the cookie too), and the key is forgotten here. A key the server no longer knows is dropped and there is nobody to move.
 * Any other failure is passed on — the key is kept for the next try, not lost to a passing error.
 */
async function adoptLegacyKey(language: Language): Promise<WebSession | null> {
  const key = legacyKey();
  if (!key) return null;
  try {
    // ★The key alone, no cookie: `me` has just found none (and a refused cookie was cleared by its answer). The call must still be `credentials: "include"` —
    //   a browser ignores the `Set-Cookie` of an `omit` call, so the session this call gives would never be kept (found by the mock-server suite, 2026-10-04).
    const response = await send(`${API_BASE}/v1/web/auth/adopt`, { method: "POST", headers: { "X-User-Key": key }, credentials: "include" }, language);
    const adopted = sessionOf(await response.json());
    if (!adopted) throw new LiveError("bad_session", translator(language)("서버가 세션 정보를 주지 않았어요.", "The server did not give the session details."));
    forgetLegacyKey();
    return adopted;
  } catch (error) {
    if (!(error instanceof LiveError) || error.code !== "unauthenticated") throw error;
    forgetLegacyKey();
    return null;
  }
}

let probing: Promise<WebSession | null> | null = null;

/**
 * Ask the server who this browser is (`GET /v1/web/auth/me`). ★Never makes a NEW user: a visitor who has not started anything is "no session".
 * A browser that still holds a key from an older version is moved to a session here (`adoptLegacyKey`) — that is the same user, not a new one.
 * Concurrent calls share one request. A server that cannot be asked throws (and `failed` is set).
 */
export function probeSession(language: Language, force = false): Promise<WebSession | null> {
  if (snapshot.probed && !snapshot.failed && !force) return Promise.resolve(snapshot.session);
  probing ??= (async () => {
    try {
      let session: WebSession | null;
      try {
        const response = await send(`${API_BASE}/v1/web/auth/me`, { credentials: "include" }, language);
        session = sessionOf(await response.json());
        if (!session) throw new LiveError("bad_session", translator(language)("서버가 세션 정보를 주지 않았어요.", "The server did not give the session details."));
        forgetLegacyKey();                                          // the cookie is who this is now
      } catch (error) {
        if (!(error instanceof LiveError) || error.code !== "unauthenticated") throw error;
        session = await adoptLegacyKey(language);
      }
      setSnapshot({ probed: true, failed: false, session });
      return session;
    } catch (error) {
      setSnapshot({ probed: true, failed: true, session: null });
      throw error;
    }
  })().finally(() => { probing = null; });
  return probing;
}

/** True when this browser has a session (asks the server once; a trip list is not asked for, and no user made, by a visitor who has none). */
export async function hasSession(language: Language): Promise<boolean> {
  return Boolean(await probeSession(language));
}

let creating: Promise<WebSession> | null = null;

/**
 * The session of this browser, made on first use. Order: the session the cookie already has → a key an older version of this page kept
 * (moved to a session, see `probeSession`) → a new guest session. `humanToken` is the Turnstile token when the human check is on — a
 * sign-up flood comes in here, so the server checks it (`{"turnstile_token"}`). Concurrent first calls share one request.
 */
export function ensureSession(language: Language, humanToken?: string | null): Promise<WebSession> {
  creating ??= (async () => {
    const known = await probeSession(language);
    if (known) return known;
    // ★Keep `method` inside the call — a reader of this file (the server contract test) takes a call whose method it cannot read for a GET.
    const response = await send(`${API_BASE}/v1/web/auth/session`, {
      method: "POST", credentials: "include",
      ...(humanToken ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify({ turnstile_token: humanToken }) } : {}),
    }, language);
    const session = sessionOf(await response.json());
    if (!session) throw new LiveError("bad_session", translator(language)("서버가 세션 정보를 주지 않았어요.", "The server did not give the session details."));
    setSnapshot({ probed: true, failed: false, session });
    return session;
  })().finally(() => { creating = null; });
  return creating;
}

/** Start a session now, with the human check's token when the check is on (the registration screen does this before it sends anything). */
export function startSession(language: Language, humanToken?: string | null): Promise<WebSession> {
  return ensureSession(language, humanToken);
}

/** The session ended on the server (a rotated, expired or removed session): forget it and say so plainly. */
export function sessionChecked(error: unknown, language: Language): unknown {
  if (!(error instanceof LiveError) || error.code !== "unauthenticated") return error;
  setSnapshot({ probed: true, failed: false, session: null });
  return new LiveError("session_expired", translator(language)("로그인 상태가 끝났어요. 다음 요청부터 새 게스트로 시작해요 — 게스트로 만든 여행은 다시 열 수 없고, 로그인한 계정의 여행은 로그인하면 다시 열려요.", "Your session has ended. The next request starts a new guest session — trips made as a guest cannot be opened again; trips of a signed-in account open again when you sign in."));
}

/**
 * A call that needs no session (which sign-in methods the server has, the exchange of a sign-in ticket). ★It never makes a session:
 * `api` would create a new user just to ask a question that has nothing to do with one. It still carries the cookie, so the server
 * sees the guest session a sign-in replaces.
 */
export async function openApi<T>(path: string, language: Language, init: RequestInit = {}): Promise<T> {
  const response = await send(`${API_BASE}${path}`, withSession(init, snapshot.session), language);
  return await response.json() as T;
}

/**
 * A request with the session. The session is made on first use (guest). A write the server refuses for its token (`403 csrf_failed`)
 * gets the token again and goes once more — nothing was done the first time. A 401 means the session ended: it is forgotten and said
 * plainly (see `sessionChecked`); we do NOT quietly make a new one and retry, or the old trips would silently disappear from view.
 */
export async function api<T>(path: string, language: Language, init: RequestInit = {}): Promise<T> {
  let session = await ensureSession(language);
  for (let attempt = 0; ; attempt += 1) {
    try {
      const response = await send(`${API_BASE}${path}`, withSession(init, session), language);
      return await response.json() as T;
    } catch (error) {
      if (attempt === 0 && error instanceof LiveError && error.code === "csrf_failed") {
        const fresh = await probeSession(language, true);
        if (fresh) { session = fresh; continue; }
      }
      if (error instanceof LiveError && error.code === "consent_required" && typeof window !== "undefined") window.dispatchEvent(new Event(CONSENT_REQUIRED_EVENT));
      throw sessionChecked(error, language);
    }
  }
}

/** The request to open a stream or send a streamed write: the session is made first, then the cookie and (on a write) the token go along. */
export async function sessionInit(language: Language, init: RequestInit = {}): Promise<RequestInit> {
  return withSession(init, await ensureSession(language));
}

/** End the session on the server (`POST /v1/web/auth/logout`) and forget it here. A session that was already over counts as done. */
export async function logout(language: Language): Promise<void> {
  try { await send(`${API_BASE}/v1/web/auth/logout`, withSession({ method: "POST" }, snapshot.session), language); }
  catch (error) { if (!(error instanceof LiveError) || error.code !== "unauthenticated") throw error; }
  setSnapshot({ probed: true, failed: false, session: null });
}
