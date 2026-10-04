import { resetSessionState } from "./client";

/**
 * Test kit for the cookie session (`[2026-10-04]`): a `fetch` that answers the session calls the way the server does, so a test of anything
 * else (`api`, the streams, the gateway) does not have to. Used by the unit tests only — the app never imports it.
 */
export const CSRF = "csrf-test";

export const sessionBody = (kind: "guest" | "member" = "guest") => ({
  kind, csrf_token: CSRF, ...(kind === "guest" ? { guest_idle_hours: 168 } : {}),
  idle_expires_at: "2026-10-12T00:00:00+00:00", absolute_expires_at: "2026-11-01T00:00:00+00:00",
});

const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const unauthenticated = () => reply({ error: { code: "unauthenticated", message: "로그인 상태가 아니에요" } }, 401);

type Call = { url: string; init: RequestInit };
/** The session calls (`/v1/web/auth/me` · `session` · `adopt` · `logout`) seen since the last `answeringSession`, oldest first. */
export const sessionCalls: Call[] = [];

/**
 * @param inner  answers every other call
 * @param has    a session cookie is already there (`me` answers 200) — false = a first visit (`me` answers 401)
 * @param kind   what the cookie's session is
 */
export function answeringSession(inner: (url: string, init: RequestInit) => Promise<Response>, { has = true, kind = "guest" }: { has?: boolean; kind?: "guest" | "member" } = {}) {
  resetSessionState();
  sessionCalls.length = 0;
  let cookie = has;
  const fetcher = async (url: string, init: RequestInit = {}): Promise<Response> => {
    const path = new URL(url).pathname;
    if (path === "/v1/web/auth/me" || path === "/v1/web/auth/session" || path === "/v1/web/auth/adopt" || path === "/v1/web/auth/logout") {
      sessionCalls.push({ url, init });
      if (path === "/v1/web/auth/me") return cookie ? reply(sessionBody(kind)) : unauthenticated();
      if (path === "/v1/web/auth/logout") { cookie = false; return reply({ status: "signed_out" }); }
      cookie = true;
      return reply(sessionBody("guest"), 201);
    }
    return inner(url, init);
  };
  return fetcher;
}
