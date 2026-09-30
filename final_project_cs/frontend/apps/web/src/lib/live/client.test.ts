import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { adoptKey, api, currentKey, dismissKeyNotice, issueKey, LiveError, pendingKeyNotice, rotateKey, userKey, waitText } from "./client";

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

  it("저장소가 전부 막혀도 동시·후속 요청은 한 번 발급한 키를 쓰고 안내를 유지한다", async () => {
    vi.resetModules();
    const client = await import("./client");
    const denied = () => { throw new Error("storage denied"); };
    vi.stubGlobal("window", { localStorage: { getItem: denied, setItem: denied, removeItem: denied }, dispatchEvent: () => true });
    replies.push(json({ user_key: "acop_u_page", notice: "보관해 주세요" }, 201), json({}), json({}), json({}));
    await Promise.all([client.api("/v1/web/trips", "ko"), client.api("/v1/web/trips", "ko")]);
    await client.api("/v1/web/trips", "ko");
    expect(calls.filter((call) => call.url.endsWith("/session"))).toHaveLength(1);
    expect(calls.slice(1).map((call) => new Headers(call.init.headers).get("X-User-Key"))).toEqual(Array(3).fill("acop_u_page"));
    expect(client.currentKey()).toBe("acop_u_page");
    expect(client.isKeyTemporary()).toBe(true);
    expect(client.pendingKeyNotice()).toEqual({ notice: "보관해 주세요" });
    client.dismissKeyNotice();
    expect(client.pendingKeyNotice()).toBeNull();
    expect(client.currentKey()).toBe("acop_u_page");
  });

  it("쓰기만 막혀 옛 키가 저장소에 남아도 가져온 키와 재발급한 키를 쓰며, 거절되면 메모리에서도 지운다", async () => {
    vi.resetModules();
    const client = await import("./client");
    const storage = memory({ [KEY]: "acop_u_old" });
    vi.stubGlobal("window", { localStorage: { ...storage, setItem: () => { throw new Error("quota"); }, removeItem: () => { throw new Error("denied"); } }, dispatchEvent: () => true });
    replies.push(json({ trips: [] }), json({ user_key: "acop_u_rotated", notice: "새 키" }));
    await client.adoptKey("acop_u_other", "ko");
    expect(client.currentKey()).toBe("acop_u_other");
    expect(client.pendingKeyNotice()).toEqual({ notice: null });
    await client.rotateKey("ko");
    expect(new Headers(calls[1].init.headers).get("X-User-Key")).toBe("acop_u_other");
    expect(client.currentKey()).toBe("acop_u_rotated");
    expect(storage.getItem(KEY)).toBe("acop_u_old");
    replies.push(json({ error: { code: "unauthenticated" } }, 401));
    await expect(client.api("/v1/web/trips", "ko")).rejects.toMatchObject({ code: "key_rejected" });
    expect(client.currentKey()).toBeNull();
    expect(client.pendingKeyNotice()).toBeNull();
  });

  it("키를 발급한 뒤 저장소 읽기가 막혀도 페이지의 키를 유지한다", async () => {
    vi.resetModules();
    const client = await import("./client");
    stub();
    replies.push(json({ user_key: "acop_u_page" }, 201));
    await client.issueKey("ko");
    window.localStorage.getItem = () => { throw new Error("denied"); };
    expect(await client.userKey("ko")).toBe("acop_u_page");
    expect(calls).toHaveLength(1);
    expect(client.isKeyTemporary()).toBe(true);
  });

  it.each([200, 401])("이전 키의 늦은 %s 응답은 새 사용자 자료가 되거나 새 키를 지우지 않는다", async (status) => {
    vi.resetModules();
    const client = await import("./client");
    stub({ [KEY]: "acop_u_old" });
    let finish!: (response: Response) => void;
    const oldResponse = new Promise<Response>((resolve) => { finish = resolve; });
    let started!: () => void;
    const called = new Promise<void>((resolve) => { started = resolve; });
    vi.stubGlobal("fetch", (_url: string, init: RequestInit) => {
      if (new Headers(init.headers).get("X-User-Key") === "acop_u_old") { started(); return oldResponse; }
      return Promise.resolve(json({ trips: [] }));
    });
    const pending = client.api("/v1/web/trips", "ko");
    await called;
    await client.adoptKey("acop_u_new", "ko");
    const rejected = expect(pending).rejects.toMatchObject({ code: status === 401 ? "key_rejected" : "key_changed" });
    finish(json(status === 401 ? { error: { code: "unauthenticated" } } : { trips: ["old user's data"] }, status));
    await rejected;
    expect(client.currentKey()).toBe("acop_u_new");
  });
});
