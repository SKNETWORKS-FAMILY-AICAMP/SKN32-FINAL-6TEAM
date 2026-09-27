import { translator, type Language } from "../i18n";

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

let pendingKey: Promise<string> | null = null;

function storedKey(): string | null {
  try { return window.localStorage.getItem(KEY_STORAGE); }
  catch { return null; }
}

function storeKey(key: string) {
  try { window.localStorage.setItem(KEY_STORAGE, key); }
  catch { /* private window: the key lives only for this page */ }
}

/** The user key, issued on first use. Concurrent first calls share one issue request. */
export async function userKey(language: Language): Promise<string> {
  const existing = storedKey();
  if (existing) return existing;
  pendingKey ??= (async () => {
    const response = await send(`${API_BASE}/v1/web/session`, { method: "POST" }, language);
    const body = await response.json() as { user_key: string };
    storeKey(body.user_key);
    return body.user_key;
  })().finally(() => { pendingKey = null; });
  return pendingKey;
}

export function currentKey(): string | null {
  return typeof window === "undefined" ? null : storedKey();
}

async function send(url: string, init: RequestInit, language: Language): Promise<Response> {
  const t = translator(language);
  let response: Response;
  try { response = await fetch(url, init); }
  catch { throw new LiveError("network", t("서버에 연결하지 못했어요. 잠시 뒤 다시 시도해 주세요.", "Could not reach the server. Please try again shortly.")); }
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
  throw new LiveError(code, message, detail);
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
