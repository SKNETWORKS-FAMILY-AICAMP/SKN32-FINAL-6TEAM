import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { adoptKey, answerWithin, api, currentKey, dismissKeyNotice, issueKey, LiveError, pendingKeyNotice, rotateKey, userKey, waitText } from "./client";

function memory(initial: Record<string, string> = {}) {
  const items = new Map<string, string>(Object.entries(initial));
  return { getItem: (key: string) => items.get(key) ?? null, setItem: (key: string, value: string) => { items.set(key, value); }, removeItem: (key: string) => { items.delete(key); } };
}

const KEY = "tripilot.web.user-key.v1";
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

describe("the user key the browser keeps", () => {
  let calls: { url: string; init: RequestInit }[];
  let replies: Response[];
  let events: number;

  function stub(storage: Record<string, string> = {}) {
    vi.stubGlobal("window", { localStorage: memory(storage), sessionStorage: memory(), dispatchEvent: () => { events += 1; return true; } });
  }

  beforeEach(() => {
    calls = [];
    replies = [];
    events = 0;
    vi.stubGlobal("fetch", async (url: string, init: RequestInit) => { calls.push({ url, init }); return replies.shift() ?? json({}); });
  });
  afterEach(() => vi.unstubAllGlobals());

  it("keeps the server's own sentence about a newly issued key until the customer says they saved it", async () => {
    stub();
    replies.push(json({ user_key: "acop_u_new", notice: "이 키를 따로 잘 보관해 주세요." }, 201));
    expect(await userKey("ko")).toBe("acop_u_new");
    expect(currentKey()).toBe("acop_u_new");
    expect(pendingKeyNotice()).toEqual({ notice: "이 키를 따로 잘 보관해 주세요." });
    expect(events).toBeGreaterThan(0);
    dismissKeyNotice();
    expect(pendingKeyNotice()).toBeNull();
  });

  it("issues a key with the human-check token in the JSON body, and without a body when there is no token", async () => {
    stub();
    replies.push(json({ user_key: "acop_u_checked", human_check: "passed" }, 201));
    expect(await issueKey("ko", "XXXX.DUMMY.TOKEN.XXXX")).toBe("acop_u_checked");
    expect(calls[0].url).toMatch(/\/v1\/web\/session$/);
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ turnstile_token: "XXXX.DUMMY.TOKEN.XXXX" });
    stub();
    replies.push(json({ user_key: "acop_u_plain" }, 201));
    await issueKey("ko");
    expect(calls[1].init.body).toBeUndefined();
  });

  it("adds when a limit opens again to the server's sentence (body seconds first, else Retry-After)", async () => {
    stub({ [KEY]: "acop_u_mine" });
    replies.push(json({ error: { code: "usage_limit", message: "오늘 계획 읽기 횟수를 다 썼다", limit: "per_key", action: "intake", used: 4, cap: 4, retry_after_seconds: 12_000 } }, 429));
    await expect(api("/v1/web/trip-intakes", "ko", { method: "POST" })).rejects.toMatchObject({ code: "usage_limit", message: "오늘 계획 읽기 횟수를 다 썼다 (3시간 20분 뒤에 다시 할 수 있어요.)" });
    replies.push(new Response(JSON.stringify({ error: { code: "service_daily_cap", message: "오늘은 더 받지 않는다" } }), { status: 503, headers: { "Retry-After": "90" } }));
    await expect(api("/v1/web/trip-intakes", "ko", { method: "POST" })).rejects.toMatchObject({ code: "service_daily_cap", message: "오늘은 더 받지 않는다 (2분 뒤에 다시 할 수 있어요.)" });
  });

  it("writes the wait in whole minutes, rounded up", () => {
    const t = (ko: string) => ko;
    expect(waitText(30, t)).toBe("(1분 뒤에 다시 할 수 있어요.)");
    expect(waitText(3600, t)).toBe("(1시간 뒤에 다시 할 수 있어요.)");
    expect(waitText(3661, t)).toBe("(1시간 2분 뒤에 다시 할 수 있어요.)");
  });

  it("does not ask for a new key when one is stored, and shows nothing", async () => {
    stub({ [KEY]: "acop_u_mine" });
    expect(await userKey("ko")).toBe("acop_u_mine");
    expect(calls).toHaveLength(0);
    expect(pendingKeyNotice()).toBeNull();
  });

  it("uses a key the customer already has only after the server accepts it", async () => {
    stub({ [KEY]: "acop_u_old" });
    replies.push(json({ trips: [] }));
    await adoptKey("  acop_u_other  ", "ko");
    expect(new Headers(calls[0].init.headers).get("X-User-Key")).toBe("acop_u_other");
    expect(currentKey()).toBe("acop_u_other");
  });

  it("refuses a key the server does not know and leaves the stored one as it was", async () => {
    stub({ [KEY]: "acop_u_old" });
    replies.push(json({ error: { code: "unauthenticated", message: "사용자 키가 없거나 맞지 않는다" } }, 401));
    await expect(adoptKey("acop_u_wrong", "ko")).rejects.toMatchObject({ code: "unauthenticated" });
    expect(currentKey()).toBe("acop_u_old");
    expect(pendingKeyNotice()).toBeNull();
  });

  it("refuses an empty key without calling the server", async () => {
    stub({ [KEY]: "acop_u_old" });
    await expect(adoptKey("   ", "ko")).rejects.toBeInstanceOf(LiveError);
    expect(calls).toHaveLength(0);
    expect(currentKey()).toBe("acop_u_old");
  });

  it("stores the rotated key at once and shows it, because the old one stops working", async () => {
    stub({ [KEY]: "acop_u_old" });
    replies.push(json({ user_key: "acop_u_rotated", notice: "새 키예요. 옛 키는 더 이상 쓸 수 없어요." }));
    await rotateKey("ko");
    expect(new Headers(calls[0].init.headers).get("X-User-Key")).toBe("acop_u_old");
    expect(calls[0].url.endsWith("/v1/web/session/rotate")).toBe(true);
    expect(currentKey()).toBe("acop_u_rotated");
    expect(pendingKeyNotice()).toEqual({ notice: "새 키예요. 옛 키는 더 이상 쓸 수 없어요." });
  });
});

// 2026-10-01: a server that never answers (its database stopped) must not leave a screen waiting for good.
describe("a call that gets no answer", () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it("ends with 'the server is not answering' instead of waiting forever, and says so apart from 'cannot connect'", async () => {
    vi.stubGlobal("window", { localStorage: memory({ [KEY]: "acop_u_mine" }), sessionStorage: memory(), dispatchEvent: () => true });
    // The limit is the platform's own timer, which fake timers do not move: hand the call a signal this test fires.
    const limit = new AbortController();
    vi.spyOn(AbortSignal, "timeout").mockReturnValue(limit.signal);
    // A server that accepts the call and never replies: the promise ends only when the call is aborted.
    vi.stubGlobal("fetch", (_url: string, init: RequestInit) => new Promise((_resolve, reject) => {
      init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "TimeoutError")));
    }));
    const failure = api("/v1/web/trips", "ko").catch((error: unknown) => error);
    await new Promise((resolve) => setTimeout(resolve, 0));   // the call is out and waiting
    limit.abort();
    const error = await failure;
    expect(error).toBeInstanceOf(LiveError);
    expect((error as LiveError).code).toBe("timeout");
    expect((error as LiveError).message).toContain("응답하지 않아요");
  });

  it("is still 'cannot connect' when the connection itself fails", async () => {
    vi.stubGlobal("window", { localStorage: memory({ [KEY]: "acop_u_mine" }), sessionStorage: memory(), dispatchEvent: () => true });
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
