import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetSessionState } from "./client";
import { getProfile } from "./profile";
import { answeringSession, CSRF } from "./session-kit";
import { countdownText, disconnectTelegram, secondsLeft, startTelegramConnect, telegramLinkOk, testTelegram } from "./telegram-connect";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

describe("the address the browser may be sent to", () => {
  it("is Telegram's own site over https (t.me and telegram.me)", () => {
    expect(telegramLinkOk("https://t.me/tripilot_alert_bot?start=Ab1_-x")).toBe(true);
    expect(telegramLinkOk("https://telegram.me/tripilot_alert_bot?start=Ab1_-x")).toBe(true);
  });

  it("refuses look-alikes, plain http, other schemes and addresses with a user part - an address the server hands out is not trusted blindly", () => {
    expect(telegramLinkOk("https://t.me.evil.example/tripilot_alert_bot")).toBe(false);
    expect(telegramLinkOk("https://evil-t.me/x")).toBe(false);
    expect(telegramLinkOk("https://nott.me/x")).toBe(false);
    expect(telegramLinkOk("https://sub.t.me/x")).toBe(false);
    expect(telegramLinkOk("https://t.me:8443/x")).toBe(false);
    expect(telegramLinkOk("http://t.me/x")).toBe(false);
    expect(telegramLinkOk("https://t.me@evil.example/x")).toBe(false);
    expect(telegramLinkOk("https://user@evil.example@t.me.evil.example/")).toBe(false);
    expect(telegramLinkOk("tg://resolve?domain=tripilot_alert_bot")).toBe(false);
    expect(telegramLinkOk("javascript:alert(1)")).toBe(false);
    expect(telegramLinkOk("")).toBe(false);
  });

  it("lets a development server use a loopback address (the tests' mock of Telegram's page) and nothing else on http", () => {
    expect(telegramLinkOk("http://127.0.0.1:8043/__test/telegram-open?code=abc")).toBe(true);
    expect(telegramLinkOk("http://localhost:3000/x")).toBe(true);
    expect(telegramLinkOk("http://[::1]:3000/x")).toBe(true);
    expect(telegramLinkOk("http://192.168.0.5/x")).toBe(false);
    expect(telegramLinkOk("http://127.0.0.1.evil.example/x")).toBe(false);
  });
});

describe("the countdown", () => {
  it("counts whole seconds up to the moment the code stops working, and never below zero", () => {
    expect(secondsLeft(10_000, 0)).toBe(10);
    expect(secondsLeft(10_000, 9_001)).toBe(1);
    expect(secondsLeft(10_000, 10_000)).toBe(0);
    expect(secondsLeft(10_000, 25_000)).toBe(0);
  });

  it("is written as mm:ss", () => {
    expect(countdownText(600)).toBe("10:00");
    expect(countdownText(581)).toBe("09:41");
    expect(countdownText(59)).toBe("00:59");
    expect(countdownText(0)).toBe("00:00");
    expect(countdownText(-3)).toBe("00:00");
  });
});

describe("talking to the server", () => {
  let calls: { url: string; init: RequestInit }[];
  let replies: Response[];
  const header = (call: { init: RequestInit }, name: string) => (call.init.headers as Record<string, string>)[name];

  beforeEach(() => {
    calls = [];
    replies = [];
    vi.stubGlobal("window", { localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} }, dispatchEvent: () => true });
    vi.stubGlobal("fetch", answeringSession(async (url, init) => { calls.push({ url, init }); return replies.shift() ?? json({}); }, { kind: "member" }));
  });
  afterEach(() => { vi.unstubAllGlobals(); resetSessionState(); });

  it("starting asks the server (a write: the CSRF token goes along) and hands back Telegram's link with when it stops working", async () => {
    replies.push(json({ link: "https://t.me/tripilot_alert_bot?start=Ab1_-x", expires_at: "2026-10-05T10:10:00+09:00" }));
    await expect(startTelegramConnect("ko")).resolves.toEqual({ link: "https://t.me/tripilot_alert_bot?start=Ab1_-x", expiresAt: "2026-10-05T10:10:00+09:00" });
    expect(calls[0].url).toMatch(/\/v1\/web\/profile\/telegram\/connect\/start$/);
    expect(calls[0].init.method).toBe("POST");
    expect(header(calls[0], "X-CSRF-Token")).toBe(CSRF);
  });

  it("refuses an answer with no link, or a link that is not Telegram's - in the customer's language", async () => {
    replies.push(json({ expires_at: "2026-10-05T10:10:00+09:00" }));
    await expect(startTelegramConnect("ko")).rejects.toMatchObject({ code: "bad_telegram_link", message: "서버가 텔레그램 연결 주소를 주지 않았어요." });
    replies.push(json({ link: "https://t.me.evil.example/bot?start=x", expires_at: "2026-10-05T10:10:00+09:00" }));
    await expect(startTelegramConnect("ko")).rejects.toMatchObject({ code: "bad_telegram_link" });
    replies.push(json({ link: 42, expires_at: "2026-10-05T10:10:00+09:00" }));
    await expect(startTelegramConnect("en")).rejects.toMatchObject({ code: "bad_telegram_link", message: "The server did not give a Telegram connection address." });
  });

  it("refuses an answer that does not say when the link stops working - a countdown is not made up", async () => {
    replies.push(json({ link: "https://t.me/tripilot_alert_bot?start=x" }));
    await expect(startTelegramConnect("ko")).rejects.toMatchObject({ code: "bad_telegram_expiry" });
    replies.push(json({ link: "https://t.me/tripilot_alert_bot?start=x", expires_at: "soon" }));
    await expect(startTelegramConnect("ko")).rejects.toMatchObject({ code: "bad_telegram_expiry" });
  });

  it("passes the server's own refusal on (a limit, no bot set up)", async () => {
    replies.push(json({ error: { code: "too_many_requests", message: "잠시 뒤에 다시 해 주세요" } }, 429));
    await expect(startTelegramConnect("ko")).rejects.toMatchObject({ code: "too_many_requests", message: "잠시 뒤에 다시 해 주세요" });
    replies.push(json({ error: { code: "not_found", message: "resource not found" } }, 404));
    await expect(startTelegramConnect("ko")).rejects.toMatchObject({ code: "not_found" });
  });

  it("a test message is a POST with the token and answers the result with the profile (read the same way as every profile)", async () => {
    replies.push(json({ result: "blocked", profile: { telegram_connect: { available: true }, telegram: { connected: true, status: "blocked", connected_at: "2026-10-05T10:00:00+09:00" }, notice_channel: "telegram" } }));
    const answer = await testTelegram("ko");
    expect(answer.result).toBe("blocked");
    expect(answer.profile.telegram).toEqual({ connected: true, status: "blocked", connectedAt: "2026-10-05T10:00:00+09:00" });
    expect(answer.profile.noticeChannel).toBe("telegram");
    expect(calls[0].url).toMatch(/\/v1\/web\/profile\/telegram\/test$/);
    expect(calls[0].init.method).toBe("POST");
    expect(header(calls[0], "X-CSRF-Token")).toBe(CSRF);
  });

  it("counts a result word it does not know as a failure - never as sent", async () => {
    replies.push(json({ result: "delivered", profile: { telegram: { connected: true, status: "ok" } } }));
    expect((await testTelegram("ko")).result).toBe("failed");
    replies.push(json({ profile: { telegram: { connected: true, status: "ok" } } }));
    expect((await testTelegram("ko")).result).toBe("failed");
  });

  it("an answer with no profile is not read as 'nothing connected' - the profile is asked again", async () => {
    replies.push(json({ result: "ok" }));
    replies.push(json({ telegram_connect: { available: true }, telegram: { connected: true, status: "ok" } }));
    const answer = await testTelegram("ko");
    expect(answer.profile.telegramConnect).toBe(true);
    expect(answer.profile.telegram.connected).toBe(true);
    expect(calls.map((call) => call.init.method ?? "GET")).toEqual(["POST", "GET"]);
    expect(calls[1].url).toMatch(/\/v1\/web\/profile$/);
  });

  it("letting go is a DELETE with the token and answers the profile as it is now", async () => {
    replies.push(json({ profile: { telegram_connect: { available: true }, telegram: { connected: false, status: null, connected_at: null }, notice_channel: null } }));
    const profile = await disconnectTelegram("ko");
    expect(profile.telegram.connected).toBe(false);
    expect(profile.noticeChannel).toBeNull();
    expect(calls[0].url).toMatch(/\/v1\/web\/profile\/telegram$/);
    expect(calls[0].init.method).toBe("DELETE");
    expect(header(calls[0], "X-CSRF-Token")).toBe(CSRF);
  });

  it("reads the telegram words of a profile only when the server says them (an older server's profile has none)", async () => {
    replies.push(json({ discord_webhook: { set: false } }));
    const old = await getProfile("ko");
    expect(old.telegramConnect).toBe(false);
    expect(old.telegram).toEqual({ connected: false, status: null, connectedAt: null });
    expect(old.noticeChannel).toBeNull();
    replies.push(json({ telegram_connect: { available: "yes" }, telegram: { connected: "true", status: "fine" }, notice_channel: "sms" }));
    const odd = await getProfile("ko");
    expect(odd.telegramConnect).toBe(false);
    expect(odd.telegram).toEqual({ connected: false, status: null, connectedAt: null });
    expect(odd.noticeChannel).toBeNull();
  });
});
