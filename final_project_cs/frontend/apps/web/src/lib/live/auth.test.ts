import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clearFlow, exchangeTicket, getAuthProviders, getLinks, isSocialUnsupported, localPath, pendingFlow, socialErrorText, startSocial, unlinkSocial } from "./auth";
import { LiveError } from "./client";

function memory(initial: Record<string, string> = {}) {
  const items = new Map<string, string>(Object.entries(initial));
  return { getItem: (key: string) => items.get(key) ?? null, setItem: (key: string, value: string) => { items.set(key, value); }, removeItem: (key: string) => { items.delete(key); } };
}
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const FLOW = "tripilot.web.auth.flow.v1";
const ko = (korean: string) => korean;

describe("social sign-in calls", () => {
  let calls: { url: string; init: RequestInit }[];
  let replies: Response[];
  let session: ReturnType<typeof memory>;

  beforeEach(() => {
    calls = [];
    replies = [];
    session = memory();
    vi.stubGlobal("window", { localStorage: memory({ "tripilot.web.user-key.v1": "acop_u_mine" }), sessionStorage: session, dispatchEvent: () => true });
    vi.stubGlobal("fetch", async (url: string, init: RequestInit) => { calls.push({ url, init }); return replies.shift() ?? json({}); });
  });
  afterEach(() => vi.unstubAllGlobals());

  const headerOf = (index: number, name: string) => (calls[index].init.headers as Record<string, string> | undefined)?.[name];

  it("asks which providers the server has without a key, keeps the names it knows and drops the rest", async () => {
    replies.push(json({ providers: [{ id: "google" }, { id: "weird" }, { id: "kakao" }, {}] }));
    expect(await getAuthProviders("ko")).toEqual(["google", "kakao"]);
    expect(calls[0].url).toMatch(/\/v1\/web\/auth\/providers$/);
    expect(headerOf(0, "X-User-Key")).toBeUndefined();
    replies.push(json({}));
    expect(await getAuthProviders("ko")).toEqual([]);                      // none set up is an empty list, not an error
  });

  it("tells an older server (404) apart from a failure", async () => {
    replies.push(json({ error: { code: "not_found", message: "no" } }, 404));
    const error = await getAuthProviders("ko").catch((failure: unknown) => failure);
    expect(isSocialUnsupported(error)).toBe(true);
    expect(isSocialUnsupported(new LiveError("timeout", "느려요"))).toBe(false);
  });

  it("starts a link with the key of this browser and a nonce, and keeps the flow for the page it comes back to", async () => {
    replies.push(json({ authorize_url: "https://accounts.example/o/auth?x=1" }));
    expect(await startSocial("google", "link", "/mypage#accounts", "ko")).toBe("https://accounts.example/o/auth?x=1");
    expect(headerOf(0, "X-User-Key")).toBe("acop_u_mine");
    const body = JSON.parse(String(calls[0].init.body));
    expect(body).toMatchObject({ mode: "link" });
    expect(body.client_nonce).toMatch(/^[0-9a-f]{64}$/);
    expect(pendingFlow()).toEqual({ provider: "google", mode: "link", nonce: body.client_nonce, returnTo: "/mypage#accounts" });
  });

  it("starts a login WITHOUT any key (asking to sign in must not create a user) and sends the human-check token when given", async () => {
    replies.push(json({ authorize_url: "https://kauth.example/oauth" }));
    await startSocial("kakao", "login", "/mypage", "ko", "TOKEN");
    expect(headerOf(0, "X-User-Key")).toBeUndefined();
    expect(JSON.parse(String(calls[0].init.body))).toMatchObject({ mode: "login", turnstile_token: "TOKEN" });
  });

  it("does not follow an address that is not http(s), and remembers no flow for it", async () => {
    replies.push(json({ authorize_url: "javascript:alert(1)" }));
    await expect(startSocial("google", "login", "/", "ko")).rejects.toMatchObject({ code: "bad_authorize_url" });
    expect(pendingFlow()).toBeNull();
  });

  it("reads a stored flow only when it is whole, and returns only a path inside this site", () => {
    session.setItem(FLOW, JSON.stringify({ provider: "google", mode: "login", nonce: "a".repeat(64), returnTo: "https://evil.example/x" }));
    expect(pendingFlow()?.returnTo).toBe("/");
    session.setItem(FLOW, JSON.stringify({ provider: "google", mode: "login", nonce: "short" }));
    expect(pendingFlow()).toBeNull();
    session.setItem(FLOW, JSON.stringify({ provider: "weird", mode: "login", nonce: "a".repeat(64) }));
    expect(pendingFlow()).toBeNull();
    session.setItem(FLOW, "not json");
    expect(pendingFlow()).toBeNull();
    for (const [input, out] of [["/mypage", "/mypage"], ["//evil.example", "/"], ["https://evil.example", "/"], ["/a\\b", "/"], [undefined, "/"]] as const) expect(localPath(input)).toBe(out);
    clearFlow();
    expect(session.getItem(FLOW)).toBeNull();
  });

  it("swaps the ticket with the nonce, and brings back a key only for a sign-in", async () => {
    replies.push(json({ outcome: "signed_in", provider: "google", user_key: "acop_u_account", notice: "보관해 주세요", trips: 2 }));
    expect(await exchangeTicket("T", "n".repeat(64), "ko")).toEqual({ outcome: "signed_in", provider: "google", userKey: "acop_u_account", notice: "보관해 주세요", trips: 2 });
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ ticket: "T", client_nonce: "n".repeat(64) });
    expect(headerOf(0, "X-User-Key")).toBeUndefined();
    replies.push(json({ outcome: "linked", provider: "kakao", user_key: "acop_u_ignored", trips: 1 }));
    expect(await exchangeTicket("T2", "n".repeat(64), "ko")).toMatchObject({ outcome: "linked", userKey: null });   // a link never changes the key
  });

  it("refuses an answer it cannot trust: an unknown outcome, or a sign-in with no key", async () => {
    replies.push(json({ outcome: "weird", provider: "google" }));
    await expect(exchangeTicket("T", "n".repeat(64), "ko")).rejects.toMatchObject({ code: "bad_exchange" });
    replies.push(json({ outcome: "signed_in", provider: "google" }));
    await expect(exchangeTicket("T", "n".repeat(64), "ko")).rejects.toMatchObject({ code: "bad_exchange" });
  });

  it("passes the refusal of a used or foreign ticket on as it is (410 ticket_invalid)", async () => {
    replies.push(json({ error: { code: "ticket_invalid", message: "만료" } }, 410));
    await expect(exchangeTicket("T", "n".repeat(64), "ko")).rejects.toMatchObject({ code: "ticket_invalid" });
  });

  it("lists and unlinks with the key, keeping only providers it knows", async () => {
    replies.push(json({ links: [{ provider: "google", linked_at: "2026-10-03T10:00:00+09:00" }, { provider: "weird" }] }));
    expect(await getLinks("ko")).toEqual([{ provider: "google", linkedAt: "2026-10-03T10:00:00+09:00" }]);
    expect(headerOf(0, "X-User-Key")).toBe("acop_u_mine");
    replies.push(json({ links: [] }));
    expect(await unlinkSocial("google", "ko")).toEqual([]);
    expect(calls[1].url).toMatch(/\/v1\/web\/auth\/google$/);
    expect(calls[1].init.method).toBe("DELETE");
  });
});

describe("what the sign-in page says", () => {
  it("says each reason plainly, and an unknown reason as a failure, never as a success", () => {
    expect(socialErrorText("cancelled", ko)).toContain("취소");
    expect(socialErrorText("already_linked_elsewhere", ko)).toContain("이미 다른 토큰에 연결");
    expect(socialErrorText("ticket_invalid", ko)).toContain("처음부터 다시");
    expect(socialErrorText("something_new", ko)).toContain("로그인하지 못했어요");
  });
});
