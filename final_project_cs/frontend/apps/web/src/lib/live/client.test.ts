import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { answerWithin, api, currentSession, ensureSession, hasSession, LiveError, loginRequired, logout, probeSession, resetSessionState, sessionInit, startSession, waitText } from "./client";
import { answeringSession, CSRF, sessionBody, sessionCalls } from "./session-kit";

function memory(initial: Record<string, string> = {}) {
  const items = new Map<string, string>(Object.entries(initial));
  return { getItem: (key: string) => items.get(key) ?? null, setItem: (key: string, value: string) => { items.set(key, value); }, removeItem: (key: string) => { items.delete(key); }, items };
}

const LEGACY_KEY = "tripilot.web.user-key.v1";
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

describe("the session the browser has (cookie, never a key it keeps)", () => {
  let calls: { url: string; init: RequestInit }[];
  let replies: Response[];
  let events: number;
  let storage: ReturnType<typeof memory>;

  function stub(options: { has?: boolean; kind?: "guest" | "member"; keep?: Record<string, string> } = {}) {
    storage = memory(options.keep);
    vi.stubGlobal("window", { localStorage: storage, sessionStorage: memory(), dispatchEvent: () => { events += 1; return true; } });
    vi.stubGlobal("fetch", answeringSession(async (url, init) => { calls.push({ url, init }); return replies.shift() ?? json({}); }, options));
  }

  beforeEach(() => { calls = []; replies = []; events = 0; });
  afterEach(() => { vi.unstubAllGlobals(); resetSessionState(); });

  it("starts a guest session on first use: it asks who this is, finds nobody, and asks the server for a guest", async () => {
    stub({ has: false });
    const session = await ensureSession("ko");
    expect(session).toMatchObject({ kind: "guest", csrf: CSRF, guestIdleHours: 168 });
    expect(sessionCalls.map((call) => new URL(call.url).pathname)).toEqual(["/v1/web/auth/me", "/v1/web/auth/session"]);
    expect(sessionCalls[1].init.method).toBe("POST");
    expect(sessionCalls[1].init.credentials).toBe("include");
    expect(currentSession()).toEqual(session);
    expect(events).toBeGreaterThan(0);                              // the screen is told
  });

  it("starts a session with the human-check token in the JSON body, and without a body when there is no token", async () => {
    stub({ has: false });
    await startSession("ko", "XXXX.DUMMY.TOKEN.XXXX");
    expect(JSON.parse(String(sessionCalls[1].init.body))).toEqual({ turnstile_token: "XXXX.DUMMY.TOKEN.XXXX" });
    stub({ has: false });
    await startSession("ko");
    expect(sessionCalls[1].init.body).toBeUndefined();
  });

  it("keeps the session the cookie already has — nothing new is made, and the same asking is shared", async () => {
    stub({ has: true, kind: "member" });
    const [one, two] = await Promise.all([ensureSession("ko"), ensureSession("ko")]);
    expect(one.kind).toBe("member");
    expect(two).toEqual(one);
    expect(sessionCalls.map((call) => new URL(call.url).pathname)).toEqual(["/v1/web/auth/me"]);
  });

  it("only asks who this is when asked for 'a session or not' — a visitor with none is not made one", async () => {
    stub({ has: false });
    expect(await hasSession("ko")).toBe(false);
    expect(await probeSession("ko")).toBeNull();
    expect(sessionCalls.map((call) => new URL(call.url).pathname)).toEqual(["/v1/web/auth/me"]);   // asked once, then remembered
  });

  it("sends the cookie on every call, and the CSRF token only on a write", async () => {
    stub({ has: true });
    replies.push(json({ ok: 1 }), json({ ok: 2 }));
    await api("/v1/web/trips", "ko");
    await api("/v1/web/trips/t1/rollback", "ko", { method: "POST" });
    expect(calls[0].init.credentials).toBe("include");
    expect(calls[0].init.headers as Record<string, string>).not.toHaveProperty("X-CSRF-Token");
    expect((calls[0].init.headers as Record<string, string>)["X-User-Key"]).toBeUndefined();
    expect(calls[1].init.credentials).toBe("include");
    expect((calls[1].init.headers as Record<string, string>)["X-CSRF-Token"]).toBe(CSRF);
  });

  it("gets the token again and goes once more when the server refuses a write for its token — nothing was done the first time", async () => {
    stub({ has: true });
    replies.push(json({ error: { code: "csrf_failed", message: "토큰이 맞지 않아요" } }, 403), json({ done: true }));
    expect(await api("/v1/web/trips/t1/delete", "ko", { method: "POST" })).toEqual({ done: true });
    expect(calls).toHaveLength(2);
    expect(sessionCalls.map((call) => new URL(call.url).pathname)).toEqual(["/v1/web/auth/me", "/v1/web/auth/me"]);   // known, then asked again for the token
  });

  it("does not go round for ever: a second token refusal reaches the screen", async () => {
    stub({ has: true });
    replies.push(json({ error: { code: "csrf_failed", message: "no" } }, 403), json({ error: { code: "csrf_failed", message: "no" } }, 403));
    await expect(api("/v1/web/trips/t1/delete", "ko", { method: "POST" })).rejects.toMatchObject({ code: "csrf_failed" });
    expect(calls).toHaveLength(2);
  });

  it("forgets an ended session and says so — it does not quietly start a new guest and retry", async () => {
    stub({ has: true });
    replies.push(json({ error: { code: "unauthenticated", message: "x" } }, 401));
    await expect(api("/v1/web/trips", "ko")).rejects.toMatchObject({ code: "session_expired" });
    expect(currentSession()).toBeNull();
    expect(sessionCalls.map((call) => new URL(call.url).pathname)).toEqual(["/v1/web/auth/me"]);   // no /auth/session behind the user's back
  });

  it("moves a browser that still holds an old key to a session once, with the key alone, and forgets the key", async () => {
    stub({ has: false, keep: { [LEGACY_KEY]: "acop_u_old", "tripilot.web.user-key.notice.v1": "{}" } });
    const session = await ensureSession("ko");
    expect(session.kind).toBe("guest");
    const adopt = sessionCalls.find((call) => new URL(call.url).pathname === "/v1/web/auth/adopt")!;
    expect(adopt.init.method).toBe("POST");
    expect((adopt.init.headers as Record<string, string>)["X-User-Key"]).toBe("acop_u_old");
    expect(adopt.init.credentials).toBe("include");               // ★`include`, or the browser would not keep the cookie this call gives; none is sent now (`me` found none), so key and cookie never go together (400 ambiguous_credentials)
    expect(sessionCalls.some((call) => new URL(call.url).pathname === "/v1/web/auth/session")).toBe(false);
    expect(storage.getItem(LEGACY_KEY)).toBeNull();
    expect(storage.getItem("tripilot.web.user-key.notice.v1")).toBeNull();
  });

  it("moves an old key to a session even when the browser only LOOKS (a trip list): the same user, no new guest made", async () => {
    stub({ has: false, keep: { [LEGACY_KEY]: "acop_u_old" } });
    expect(await hasSession("ko")).toBe(true);
    expect(sessionCalls.map((call) => new URL(call.url).pathname)).toEqual(["/v1/web/auth/me", "/v1/web/auth/adopt"]);
    expect(storage.getItem(LEGACY_KEY)).toBeNull();
    expect(currentSession()).toMatchObject({ kind: "guest" });
  });

  it("drops an old key the server no longer knows and starts as a new guest; any other failure is said, and the key is kept", async () => {
    stub({ has: false, keep: { [LEGACY_KEY]: "acop_u_gone" } });
    const inner = globalThis.fetch;
    vi.stubGlobal("fetch", async (url: string, init: RequestInit) => new URL(url).pathname === "/v1/web/auth/adopt"
      ? json({ error: { code: "unauthenticated", message: "키가 맞지 않아요" } }, 401) : inner(url, init));
    expect((await ensureSession("ko")).kind).toBe("guest");
    expect(storage.getItem(LEGACY_KEY)).toBeNull();

    stub({ has: false, keep: { [LEGACY_KEY]: "acop_u_kept" } });
    const inner2 = globalThis.fetch;
    vi.stubGlobal("fetch", async (url: string, init: RequestInit) => new URL(url).pathname === "/v1/web/auth/adopt"
      ? json({ error: { code: "internal_error", message: "서버 오류" } }, 500) : inner2(url, init));
    await expect(ensureSession("ko")).rejects.toMatchObject({ code: "internal_error" });
    expect(storage.getItem(LEGACY_KEY)).toBe("acop_u_kept");        // not lost to a passing failure
  });

  it("builds the request of a stream or streamed write: the cookie, and on a write the token", async () => {
    stub({ has: true });
    const read = await sessionInit("ko", { headers: { Accept: "text/event-stream" } });
    expect(read.credentials).toBe("include");
    expect(read.headers as Record<string, string>).not.toHaveProperty("X-CSRF-Token");
    const write = await sessionInit("ko", { method: "POST", headers: { Accept: "text/event-stream" } });
    expect((write.headers as Record<string, string>)["X-CSRF-Token"]).toBe(CSRF);
  });

  it("signs out on the server and forgets the session here", async () => {
    stub({ has: true });
    await ensureSession("ko");
    await logout("ko");
    const out = sessionCalls.find((call) => new URL(call.url).pathname === "/v1/web/auth/logout")!;
    expect((out.init.headers as Record<string, string>)["X-CSRF-Token"]).toBe(CSRF);
    expect(currentSession()).toBeNull();
  });

  it("reads the session body: a member has no idle hours, a body without a token is not a session", async () => {
    stub({ has: true, kind: "member" });
    expect(await probeSession("ko")).toMatchObject({ kind: "member", guestIdleHours: null });
    expect(sessionBody("guest")).toMatchObject({ kind: "guest", guest_idle_hours: 168 });
    stub({ has: true });
    vi.stubGlobal("fetch", async () => json({ kind: "guest" }));
    await expect(probeSession("ko", true)).rejects.toMatchObject({ code: "bad_session" });
  });

  it("adds when a limit opens again to the server's sentence (body seconds first, else Retry-After)", async () => {
    stub({ has: true });
    replies.push(json({ error: { code: "usage_limit", message: "오늘 계획 읽기 횟수를 다 썼다", limit: "per_key", action: "intake", used: 4, cap: 4, retry_after_seconds: 12_000 } }, 429));
    await expect(api("/v1/web/trip-intakes", "ko", { method: "POST" })).rejects.toMatchObject({ code: "usage_limit", message: "오늘 계획 읽기 횟수를 다 썼다 (3시간 20분 뒤에 다시 할 수 있어요.)" });
    replies.push(new Response(JSON.stringify({ error: { code: "service_daily_cap", message: "오늘은 더 받지 않는다" } }), { status: 503, headers: { "Retry-After": "90" } }));
    await expect(api("/v1/web/trip-intakes", "ko", { method: "POST" })).rejects.toMatchObject({ code: "service_daily_cap", message: "오늘은 더 받지 않는다 (2분 뒤에 다시 할 수 있어요.)" });
  });

  it("tells a guest's limit from other refusals: the guest_* codes and login_required ask for a login", async () => {
    stub({ has: true });
    replies.push(json({ error: { code: "guest_trip_limit", message: "게스트는 여행을 1개까지 만들 수 있어요", login_required: true, cap: 1, existing: 1 } }, 403));
    const limit = await api("/v1/web/trip-intakes/i1/confirm", "ko", { method: "POST" }).catch((error: unknown) => error);
    expect(limit).toBeInstanceOf(LiveError);
    expect(loginRequired(limit)).toBe(true);
    expect(loginRequired(new LiveError("guest_trip_too_far", "x"))).toBe(true);
    expect(loginRequired(new LiveError("usage_limit", "x"))).toBe(false);
    expect(loginRequired(new Error("x"))).toBe(false);
  });

  it("writes the wait in whole minutes, rounded up", () => {
    const t = (ko: string) => ko;
    expect(waitText(30, t)).toBe("(1분 뒤에 다시 할 수 있어요.)");
    expect(waitText(3600, t)).toBe("(1시간 뒤에 다시 할 수 있어요.)");
    expect(waitText(3661, t)).toBe("(1시간 2분 뒤에 다시 할 수 있어요.)");
  });
});

// 2026-10-01: a server that never answers (its database stopped) must not leave a screen waiting for good.
describe("a call that gets no answer", () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); resetSessionState(); });

  it("ends with 'the server is not answering' instead of waiting forever, and says so apart from 'cannot connect'", async () => {
    vi.stubGlobal("window", { localStorage: memory(), sessionStorage: memory(), dispatchEvent: () => true });
    // The limit is the platform's own timer, which fake timers do not move: hand the call a signal this test fires.
    const limit = new AbortController();
    vi.spyOn(AbortSignal, "timeout").mockReturnValue(limit.signal);
    // A server that accepts the call and never replies: the promise ends only when the call is aborted.
    vi.stubGlobal("fetch", answeringSession((_url, init) => new Promise((_resolve, reject) => {
      init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "TimeoutError")));
    })));
    const failure = api("/v1/web/trips", "ko").catch((error: unknown) => error);
    await new Promise((resolve) => setTimeout(resolve, 0));   // the call is out and waiting
    limit.abort();
    const error = await failure;
    expect(error).toBeInstanceOf(LiveError);
    expect((error as LiveError).code).toBe("timeout");
    expect((error as LiveError).message).toContain("응답하지 않아요");
  });

  it("is still 'cannot connect' when the connection itself fails", async () => {
    vi.stubGlobal("window", { localStorage: memory(), sessionStorage: memory(), dispatchEvent: () => true });
    vi.stubGlobal("fetch", async () => { throw new TypeError("network down"); });
    const error = await api("/v1/web/trips", "ko").catch((e: unknown) => e);
    expect((error as LiveError).code).toBe("network");
  });

  it("gives the calls that read many places, wake the chat model or carry files a longer limit", () => {
    const base = "http://127.0.0.1:8042/v1/web";
    expect(answerWithin(`${base}/trips`)).toBe(60_000);
    expect(answerWithin(`${base}/trips/t1/proposals`)).toBe(60_000);
    for (const slow of ["/trips/t1/messages", "/trip-intakes", "/trip-intakes/i1/plan", "/trip-intakes/i1/confirm"]) {
      expect(answerWithin(`${base}${slow}`), slow).toBe(180_000);
    }
  });
});
