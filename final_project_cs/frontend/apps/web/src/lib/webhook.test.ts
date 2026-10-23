import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { answeringSession, sessionCalls } from "./live/session-kit";

const HOOK = "https://discord.com/api/web" + "hooks/123456789012345678/abcdefghijklmnopqrstuvwxyz0123";
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const profile = { recovery_email: null, discord_webhook: { set: true, masked: "https://discord.com/api/web" + "hooks/1234…/••••", status: "untested", checked_at: null }, updated_at: null };

describe("the Discord webhook (PUT /v1/web/profile discord_webhook_url)", () => {
  let items: Map<string, string>;
  let calls: { url: string; init: RequestInit }[];
  let replies: Response[];

  /** `has`: this browser already has a session cookie. The page's modules are loaded again for each test (the webhook waits in module memory). */
  function browser(has: boolean) {
    vi.resetModules();
    vi.stubGlobal("fetch", answeringSession(async (url, init) => { calls.push({ url, init }); return replies.shift() ?? json(profile); }, { has }));
  }

  beforeEach(() => {
    items = new Map();
    calls = [];
    replies = [];
    vi.stubGlobal("window", { localStorage: { getItem: (key: string) => items.get(key) ?? null, setItem: (key: string, value: string) => { items.set(key, value); }, removeItem: (key: string) => { items.delete(key); } }, dispatchEvent: () => true });
  });
  afterEach(() => vi.unstubAllGlobals());

  it("goes to the server at once when this browser has a session, and the masked answer comes back", async () => {
    browser(true);
    const { saveDiscordWebhook } = await import("./webhook");
    const saved = await saveDiscordWebhook(` ${HOOK} `, "ko");
    expect(saved).toMatchObject({ where: "server", profile: { webhook: { set: true, masked: "https://discord.com/api/web" + "hooks/1234…/••••", status: "untested" } } });
    expect(calls).toHaveLength(1);
    expect(calls[0].init.method).toBe("PUT");
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ discord_webhook_url: HOOK });
  });

  it("before the first session it waits in page memory only — no request, nothing in storage — and goes up once the session exists", async () => {
    browser(false);
    const { saveDiscordWebhook, syncDiscordWebhook, webhookWaiting } = await import("./webhook");
    const { ensureSession } = await import("./live/client");
    expect(await saveDiscordWebhook(HOOK, "ko")).toEqual({ where: "waiting" });
    expect(webhookWaiting()).toBe(true);
    expect(calls).toHaveLength(0);
    expect([...items.values()].some((value) => value.includes("webhooks"))).toBe(false);
    await syncDiscordWebhook("ko");
    expect(calls).toHaveLength(0);
    expect(sessionCalls.some((call) => new URL(call.url).pathname === "/v1/web/auth/session")).toBe(false);   // waiting never makes a user

    await ensureSession("ko");                                                  // the first trip starts the session
    await syncDiscordWebhook("ko");
    expect(calls.map((call) => JSON.parse(String(call.init.body)))).toEqual([{ discord_webhook_url: HOOK }]);
    expect(webhookWaiting()).toBe(false);
    await syncDiscordWebhook("ko");
    expect(calls).toHaveLength(1);
  });

  it("the session may announce itself more than once: the syncs share one request", async () => {
    browser(false);
    const { saveDiscordWebhook, syncDiscordWebhook } = await import("./webhook");
    const { ensureSession } = await import("./live/client");
    await saveDiscordWebhook(HOOK, "ko");
    await ensureSession("ko");
    await Promise.all([syncDiscordWebhook("ko"), syncDiscordWebhook("ko")]);
    expect(calls).toHaveLength(1);
  });

  it("a waiting webhook the server refuses is dropped; any other failure waits for the next session change", async () => {
    browser(false);
    const { saveDiscordWebhook, syncDiscordWebhook, webhookWaiting } = await import("./webhook");
    const { ensureSession } = await import("./live/client");
    await saveDiscordWebhook(HOOK, "ko");
    await ensureSession("ko");
    replies.push(json({ error: { code: "internal_error", message: "서버 오류" } }, 500));
    await syncDiscordWebhook("ko");
    expect(webhookWaiting()).toBe(true);
    replies.push(json({ error: { code: "invalid_webhook", message: "디스코드 웹훅 주소 모양이 아니에요" } }, 422));
    await syncDiscordWebhook("ko");
    expect(webhookWaiting()).toBe(false);
  });

  it("removing it sends null; the server's refusal reaches the screen", async () => {
    browser(true);
    const { saveDiscordWebhook } = await import("./webhook");
    await saveDiscordWebhook(null, "ko");
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ discord_webhook_url: null });
    replies.push(json({ error: { code: "invalid_webhook", message: "디스코드 웹훅 주소 모양이 아니에요" } }, 422));
    await expect(saveDiscordWebhook(HOOK, "ko")).rejects.toMatchObject({ code: "invalid_webhook" });
  });
});
