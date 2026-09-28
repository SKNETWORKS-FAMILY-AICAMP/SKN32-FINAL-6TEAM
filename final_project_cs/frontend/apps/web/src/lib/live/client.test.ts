import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { adoptKey, currentKey, dismissKeyNotice, LiveError, pendingKeyNotice, rotateKey, userKey } from "./client";

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
