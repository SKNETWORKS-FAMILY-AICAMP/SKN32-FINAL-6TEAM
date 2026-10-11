import type { Language } from "../i18n";
import { api, LiveError, openApi, sessionOf, takeSession, probeSession } from "./client";

/** 같은 소셜 진입점에서 로그인과 가입을 처리한다. 검증된 게스트 일정은 회원 계정으로 보관한다. */
export const SOCIAL_PROVIDERS = ["google", "kakao", "naver", "discord"] as const;
export type SocialProvider = (typeof SOCIAL_PROVIDERS)[number];
export type SocialMode = "login" | "link";

const NAMES: Record<SocialProvider, [string, string]> = {
  google: ["구글", "Google"], kakao: ["카카오", "Kakao"], naver: ["네이버", "Naver"], discord: ["디스코드", "Discord"],
};
export const providerName = (provider: SocialProvider): [string, string] => NAMES[provider];

const isProvider = (value: unknown): value is SocialProvider => SOCIAL_PROVIDERS.includes(value as SocialProvider);

/** An older server without these calls answers 404/405 — the screen then says it is being prepared and shows no button. */
export function isSocialUnsupported(error: unknown): boolean {
  return error instanceof LiveError && ["not_found", "method_not_allowed", "HTTP_404", "HTTP_405"].includes(error.code);
}

/** The providers the server has set up. Unknown names are dropped; an empty list means none are set up (not "unsupported"). */
export async function getAuthProviders(language: Language): Promise<SocialProvider[]> {
  const body = await openApi<{ providers?: { id?: unknown }[] }>("/v1/web/auth/providers", language);
  return (body.providers ?? []).map((entry) => entry?.id).filter(isProvider);
}

/** Where the flow was started from, kept for the page the provider sends the browser back to. */
export interface PendingFlow { provider: SocialProvider; mode: SocialMode; nonce: string; returnTo: string }
const FLOW_STORAGE = "tripilot.web.auth.flow.v1";

/** A path inside this site only (never an address, never `//host`) — the flow is read back from storage, so it is checked again here. */
export const localPath = (value: unknown): string => (typeof value === "string" && value.startsWith("/") && !value.startsWith("//") && !value.includes("\\") ? value : "/");

export function pendingFlow(): PendingFlow | null {
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(FLOW_STORAGE) ?? "null") as Partial<PendingFlow> | null;
    if (parsed && isProvider(parsed.provider) && (parsed.mode === "login" || parsed.mode === "link") && typeof parsed.nonce === "string" && parsed.nonce.length >= 32)
      return { provider: parsed.provider, mode: parsed.mode, nonce: parsed.nonce, returnTo: localPath(parsed.returnTo) };
    return null;
  } catch { return null; }
}

export function clearFlow() {
  try { window.sessionStorage.removeItem(FLOW_STORAGE); } catch { /* ignore */ }
}

/** 32 random bytes, as hex. */
function newNonce(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

/**
 * Ask the server where to send the browser (`POST /auth/{provider}/start`) and remember the flow. Returns the provider's address;
 * the caller moves the browser there. `login` with no key may be refused with `human_check_required` — the caller then asks for the check.
 */
export async function startSocial(provider: SocialProvider, mode: SocialMode, returnTo: string, language: Language, humanToken?: string | null): Promise<string> {
  await probeSession(language); // 쿠키 세션의 CSRF를 로그인 시작에도 붙인다. 새 게스트는 만들지 않는다.
  const nonce = newNonce();
  const init = {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode, client_nonce: nonce, ...(humanToken ? { turnstile_token: humanToken } : {}) }),
  };
  // `link` belongs to this browser's session; `login` is asked without making one (so no user is created just by looking).
  const answer = mode === "link"
    ? await api<{ authorize_url?: unknown }>(`/v1/web/auth/${provider}/start`, language, init)
    : await openApi<{ authorize_url?: unknown }>(`/v1/web/auth/${provider}/start`, language, init);
  const address = typeof answer.authorize_url === "string" ? answer.authorize_url : "";
  if (!/^https?:\/\//.test(address)) throw new LiveError("bad_authorize_url", "서버가 로그인 주소를 주지 않았어요.");
  try { window.sessionStorage.setItem(FLOW_STORAGE, JSON.stringify({ provider, mode, nonce, returnTo: localPath(returnTo) } satisfies PendingFlow)); } catch { /* the flow then cannot finish; the exchange says so */ }
  return address;
}

export type SocialOutcome = "signed_in" | "created" | "linked";
export interface SocialResult { outcome: SocialOutcome; provider: SocialProvider; trips: number | null }

/**
 * Swap the ticket for the result (`POST /auth/exchange`). A ticket that is old, used or not this browser's is refused (410 `ticket_invalid`).
 * ★Asked with `session: "cookie"`: a sign-in (`signed_in` · `created`) then sets the member's session cookie and brings its CSRF token; the
 *   guest session this browser had (the cookie goes along) is ended by the server. A link keeps the session — it is read again to learn it is a member's now.
 */
export async function exchangeTicket(ticket: string, nonce: string, language: Language): Promise<SocialResult> {
  const body = await openApi<{ outcome?: unknown; provider?: unknown; trips?: unknown; kind?: unknown; csrf_token?: unknown }>("/v1/web/auth/exchange", language, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ticket, client_nonce: nonce, session: "cookie" }),
  });
  const outcome = (["signed_in", "created", "linked"] as const).find((value) => value === body.outcome);
  if (!outcome || !isProvider(body.provider)) throw new LiveError("bad_exchange", "서버 답을 읽지 못했어요.");
  if (outcome === "linked") await probeSession(language, true).catch(() => null);
  else {
    // 세션을 받지 못했으면 로그인 성공으로 안내하지 않는다.
    const session = sessionOf(body) ?? await probeSession(language, true).catch(() => null);
    if (!session) throw new LiveError("bad_exchange", "서버가 로그인 세션을 주지 않았어요.");
    takeSession(session);
  }
  return { outcome, provider: body.provider, trips: typeof body.trips === "number" ? body.trips : null };
}

/** The providers linked to this browser's session (`GET /auth/links`). */
export async function getLinks(language: Language): Promise<{ provider: SocialProvider; linkedAt: string | null }[]> {
  return linksOf(await api<{ links?: { provider?: unknown; linked_at?: unknown }[] }>("/v1/web/auth/links", language));
}

const linksOf = (body: { links?: { provider?: unknown; linked_at?: unknown }[] }) =>
  (body.links ?? []).flatMap((entry) => isProvider(entry?.provider) ? [{ provider: entry.provider, linkedAt: typeof entry.linked_at === "string" ? entry.linked_at : null }] : []);

/** Unlink one provider (`DELETE /auth/{provider}`); the server answers with what is still linked. */
export async function unlinkSocial(provider: SocialProvider, language: Language): Promise<{ provider: SocialProvider; linkedAt: string | null }[]> {
  const body = await api<{ links?: { provider?: unknown; linked_at?: unknown }[] }>(`/v1/web/auth/${provider}`, language, { method: "DELETE" });
  return linksOf(body);
}

/** What the sign-in page said went wrong (`?error=`), in the customer's words. Unknown codes are said plainly, not as a success. */
export function socialErrorText(code: string, t: (ko: string, en: string) => string): string {
  switch (code) {
    case "cancelled": return t("로그인을 취소했어요.", "You cancelled the sign-in.");
    case "denied": return t("로그인 업체가 접근을 허락하지 않았어요.", "The sign-in provider did not allow access.");
    case "already_linked_elsewhere": return t("이 계정은 이미 다른 여행 기록에 연결돼 있어요. 그 계정으로 「로그인」하면 그 여행을 열 수 있어요. 이 브라우저의 지금 여행은 그대로예요.", "This account is already linked to other trips. Use “Sign in” with it to open them. The trips in this browser are unchanged.");
    case "ticket_invalid": return t("로그인 확인이 만료됐거나 이 브라우저에서 시작한 것이 아니에요. 처음부터 다시 해 주세요.", "The sign-in check expired or was not started in this browser. Please start again.");
    default: return t("로그인하지 못했어요. 잠시 뒤 다시 해 주세요.", "Could not sign in. Please try again shortly.");
  }
}
