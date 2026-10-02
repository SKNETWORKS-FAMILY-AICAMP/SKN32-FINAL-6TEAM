import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./data-mode", () => ({ DATA_MODE: "live" }));

const KEY = "tripilot.web.user-key.v1";
const HOOK = "https://discord.com/api/webhooks/123456789012345678/abcdefghijklmnopqrstuvwxyz0123";
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const profile = { recovery_email: null, discord_webhook: { set: true, masked: "https://discord.com/api/webhooks/1234…/••••", status: "untested", checked_at: null }, updated_at: null };

describe("the Discord webhook (PUT /v1/web/profile discord_webhook_url)", () => {
  let items: Map<string, string>;
  let calls: { url: string; init: RequestInit }[];
  let replies: Response[];

  beforeEach(() => {
    vi.resetModules();
    items = new Map();
    calls = [];
    replies = [];
    vi.stubGlobal("window", { localStorage: { getItem: (key: string) => items.get(key) ?? null, setItem: (key: string, value: string) => { items.set(key, value); }, removeItem: (key: string) => { items.delete(key); } }, dispatchEvent: () => true });
    vi.stubGlobal("fetch", async (url: string, init: RequestInit) => { calls.push({ url, init }); return replies.shift() ?? json(profile); });
  });
  afterEach(() => vi.unstubAllGlobals());

  it("goes to the server at once when this browser has a user key, and the masked answer comes back", async () => {
    items.set(KEY, "acop_u_known");
    const { saveDiscordWebhook } = await import("./webhook");
    const saved = await saveDiscordWebhook(` ${HOOK} `, "ko");
    expect(saved).toMatchObject({ where: "server", profile: { webhook: { set: true, masked: "https://discord.com/api/webhooks/1234…/••••", status: "untested" } } });
    expect(calls).toHaveLength(1);
    expect(calls[0].init.method).toBe("PUT");
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ discord_webhook_url: HOOK });
  });

  it("before the first key it waits in page memory only — no request, nothing in storage — and goes up once the key exists", async () => {
    const { saveDiscordWebhook, syncDiscordWebhook, webhookWaiting } = await import("./webhook");
    expect(await saveDiscordWebhook(HOOK, "ko")).toEqual({ where: "waiting" });
    expect(webhookWaiting()).toBe(true);
    expect(calls).toHaveLength(0);
    expect([...items.values()].some((value) => value.includes("webhooks"))).toBe(false);
    await syncDiscordWebhook("ko");
    expect(calls).toHaveLength(0);

    items.set(KEY, "acop_u_new");
    await syncDiscordWebhook("ko");
    expect(calls.map((call) => JSON.parse(String(call.init.body)))).toEqual([{ discord_webhook_url: HOOK }]);
    expect(webhookWaiting()).toBe(false);
    await syncDiscordWebhook("ko");
    expect(calls).toHaveLength(1);
  });

  it("a new key announces itself twice (the key, then its notice): both syncs share one request", async () => {
    const { saveDiscordWebhook, syncDiscordWebhook } = await import("./webhook");
    await saveDiscordWebhook(HOOK, "ko");
    items.set(KEY, "acop_u_new");
    await Promise.all([syncDiscordWebhook("ko"), syncDiscordWebhook("ko")]);
    expect(calls).toHaveLength(1);
  });

  it("a waiting webhook the server refuses is dropped; any other failure waits for the next key change", async () => {
    const { saveDiscordWebhook, syncDiscordWebhook, webhookWaiting } = await import("./webhook");
    await saveDiscordWebhook(HOOK, "ko");
    items.set(KEY, "acop_u_new");
    replies.push(json({ error: { code: "internal_error", message: "서버 오류" } }, 500));
    await syncDiscordWebhook("ko");
    expect(webhookWaiting()).toBe(true);
    replies.push(json({ error: { code: "invalid_webhook", message: "디스코드 웹훅 주소 모양이 아니에요" } }, 422));
    await syncDiscordWebhook("ko");
    expect(webhookWaiting()).toBe(false);
  });

  it("removing it sends null; the server's refusal reaches the screen", async () => {
    items.set(KEY, "acop_u_known");
    const { saveDiscordWebhook } = await import("./webhook");
    await saveDiscordWebhook(null, "ko");
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ discord_webhook_url: null });
    replies.push(json({ error: { code: "invalid_webhook", message: "디스코드 웹훅 주소 모양이 아니에요" } }, 422));
    await expect(saveDiscordWebhook(HOOK, "ko")).rejects.toMatchObject({ code: "invalid_webhook" });
  });
});
