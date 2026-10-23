import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetSessionState } from "./client";
import { discordAddressOk, readDiscordReturn, startDiscordConnect } from "./discord-connect";
import { getProfile } from "./profile";
import { answeringSession, CSRF } from "./session-kit";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

describe("coming back from Discord (?discord=…)", () => {
  it("reads the four answers the server's callback gives, and nothing for a page that is not a return", () => {
    expect(readDiscordReturn("?discord=connected")).toBe("connected");
    expect(readDiscordReturn("?discord=cancelled")).toBe("cancelled");
    expect(readDiscordReturn("?discord=expired")).toBe("expired");
    expect(readDiscordReturn("?discord=failed")).toBe("failed");
    expect(readDiscordReturn("")).toBeNull();
    expect(readDiscordReturn("?tab=2")).toBeNull();
  });

  it("counts a word it does not know as a failure - never as connected", () => {
    expect(readDiscordReturn("?discord=ok")).toBe("failed");
    expect(readDiscordReturn("?discord=")).toBe("failed");
    expect(readDiscordReturn("?discord=CONNECTED")).toBe("failed");
  });
});

describe("the address the browser may be sent to", () => {
  it("is Discord's own site over https (and its subdomains)", () => {
    expect(discordAddressOk("https://discord.com/oauth2/authorize?client_id=1&scope=webhook.incoming")).toBe(true);
    expect(discordAddressOk("https://canary.discord.com/oauth2/authorize")).toBe(true);
  });

  it("refuses look-alikes, plain http, and other schemes - an address the server hands out is not trusted blindly", () => {
    expect(discordAddressOk("https://discord.com.evil.example/oauth2/authorize")).toBe(false);
    expect(discordAddressOk("https://evil-discord.com/oauth2/authorize")).toBe(false);
    expect(discordAddressOk("http://discord.com/oauth2/authorize")).toBe(false);
    expect(discordAddressOk("https://user@evil.example@discord.com.evil.example/")).toBe(false);
    expect(discordAddressOk("javascript:alert(1)")).toBe(false);
    expect(discordAddressOk("")).toBe(false);
  });

  it("lets a development server use a loopback address (the tests' mock of Discord's page)", () => {
    expect(discordAddressOk("http://127.0.0.1:8043/__test/discord-connect?flow=1")).toBe(true);
    expect(discordAddressOk("http://localhost:3000/x")).toBe(true);
    expect(discordAddressOk("http://192.168.0.5/x")).toBe(false);
  });
});

describe("starting the connection", () => {
  let calls: { url: string; init: RequestInit }[];
  let replies: Response[];

  beforeEach(() => {
    calls = [];
    replies = [];
    vi.stubGlobal("window", { localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} }, dispatchEvent: () => true });
    vi.stubGlobal("fetch", answeringSession(async (url, init) => { calls.push({ url, init }); return replies.shift() ?? json({}); }, { kind: "member" }));
  });
  afterEach(() => { vi.unstubAllGlobals(); resetSessionState(); });

  it("asks the server (a write: the CSRF token goes along) and hands back Discord's address", async () => {
    replies.push(json({ authorize_url: "https://discord.com/oauth2/authorize?client_id=1&scope=webhook.incoming&state=s" }));
    await expect(startDiscordConnect("ko")).resolves.toMatch(/^https:\/\/discord\.com\/oauth2\/authorize/);
    expect(calls[0].url).toMatch(/\/v1\/web\/profile\/discord\/connect\/start$/);
    expect(calls[0].init.method).toBe("POST");
    expect((calls[0].init.headers as Record<string, string>)["X-CSRF-Token"]).toBe(CSRF);
  });

  it("refuses an answer with no address, or one that is not Discord's", async () => {
    replies.push(json({}));
    await expect(startDiscordConnect("ko")).rejects.toMatchObject({ code: "bad_authorize_url" });
    replies.push(json({ authorize_url: "https://evil.example/login" }));
    await expect(startDiscordConnect("ko")).rejects.toMatchObject({ code: "bad_authorize_url" });
  });

  it("says the server can connect only when it says so (an older server's profile has no such word)", async () => {
    replies.push(json({ discord_webhook: { set: false }, discord_connect: { available: true } }));
    expect((await getProfile("ko")).discordConnect).toBe(true);
    replies.push(json({ discord_webhook: { set: false } }));
    expect((await getProfile("ko")).discordConnect).toBe(false);
    replies.push(json({ discord_webhook: { set: false }, discord_connect: { available: "yes" } }));
    expect((await getProfile("ko")).discordConnect).toBe(false);
  });
});
