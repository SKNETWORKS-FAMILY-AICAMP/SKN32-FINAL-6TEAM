import { translator, type Language } from "../i18n";
import { api, LiveError } from "./client";
import { getProfile, read, type ServerProfile } from "./profile";

/**
 * `[2026-10-05 사용자 지시]` 「텔레그램으로 연결」 (alerts only) - the customer presses one button, Telegram opens on our bot, one tap on 「시작」 and the server
 * binds that chat to the customer; later the bot sends the plan-change alerts there. This file is the web's half of the contract
 * (`wiki/records/plans/2026-10-05_텔레그램_연결_백엔드_요청.md`):
 *   - `POST /v1/web/profile/telegram/connect/start` (session) → `{ link, expires_at }`: a one-time link (`https://t.me/<bot>?start=<code>`, 10 minutes);
 *   - the customer taps 「시작」 in Telegram, Telegram tells the server (never this page), and the profile then says `telegram.connected`;
 *   - `POST …/telegram/test` → `{ result, profile }` · `DELETE /v1/web/profile/telegram` → `{ profile }`.
 * ★Whether the row exists is the server's word (`GET /v1/web/profile` → `telegram_connect.available`): an older server, or one with no bot set up, shows no
 *   row - nothing is faked. ★The one-time code lives only inside the link; this page never writes it to storage or to its own address.
 */

/**
 * Where this browser may be sent to connect: Telegram's own site (`t.me`, `telegram.me`), over https, no look-alikes. A development server may use a
 * loopback address (the tests' mock of Telegram's page); anything else - a server that hands out some other address - is refused rather than followed.
 */
export function telegramLinkOk(address: string): boolean {
  try {
    const url = new URL(address);
    if (url.username || url.password) return false;
    if (url.protocol === "https:") return url.port === "" && (url.hostname === "t.me" || url.hostname === "telegram.me");
    return url.protocol === "http:" && ["127.0.0.1", "localhost", "[::1]"].includes(url.hostname);
  } catch {
    return false;
  }
}

export interface TelegramStart {
  /** Telegram's address with the one-time code in it. Always passes `telegramLinkOk`. */
  link: string;
  /** When the code stops working (ISO time). Always a time that can be read. */
  expiresAt: string;
}

/** Ask the server for the one-time link. Rejects when the server gives no link (or one that is not Telegram's), or no time when it stops working. */
export async function startTelegramConnect(language: Language): Promise<TelegramStart> {
  const t = translator(language);
  const answer = await api<{ link?: unknown; expires_at?: unknown }>("/v1/web/profile/telegram/connect/start", language, { method: "POST" });
  const link = typeof answer.link === "string" ? answer.link : "";
  if (!telegramLinkOk(link)) throw new LiveError("bad_telegram_link", t("서버가 텔레그램 연결 주소를 주지 않았어요.", "The server did not give a Telegram connection address."));
  // ★No time = the countdown would be made up, so the answer is refused instead (the contract always sends it).
  const expiresAt = typeof answer.expires_at === "string" ? answer.expires_at : "";
  if (Number.isNaN(Date.parse(expiresAt))) throw new LiveError("bad_telegram_expiry", t("서버가 연결 시간을 알려 주지 않았어요.", "The server did not say how long the link works."));
  return { link, expiresAt };
}

/** How a test message went: sent (`ok`), the customer blocked the bot (`blocked`), Telegram limited us, or it failed. */
export type TelegramTestResult = "ok" | "blocked" | "rate_limited" | "failed";
const RESULTS = ["ok", "blocked", "rate_limited", "failed"] as const;

type Wire = Parameters<typeof read>[0];

/**
 * The profile an answer carries; an answer without one (a server that forgot it) is not read as "nothing connected" - the profile is asked again, so the row
 * never disappears on a missing field.
 */
async function profileOf(answer: { profile?: Wire }, language: Language): Promise<ServerProfile> {
  return answer.profile ? read(answer.profile) : getProfile(language);
}

/** One test line to the connected chat, only when the customer presses it. 409 `no_telegram` and 429 `too_soon` (with a sentence) come back as errors. */
export async function testTelegram(language: Language): Promise<{ result: TelegramTestResult; profile: ServerProfile }> {
  const answer = await api<{ result?: string; profile?: Wire }>("/v1/web/profile/telegram/test", language, { method: "POST" });
  return { result: RESULTS.find((value) => value === answer.result) ?? "failed", profile: await profileOf(answer, language) };
}

/** Let go of the chat: the server forgets it, and alerts go to Discord (if one is connected) or nowhere. Answers the profile as it is now. */
export async function disconnectTelegram(language: Language): Promise<ServerProfile> {
  return profileOf(await api<{ profile?: Wire }>("/v1/web/profile/telegram", language, { method: "DELETE" }), language);
}

/** Whole seconds left until `expiresAtMs` (never below 0). */
export function secondsLeft(expiresAtMs: number, nowMs: number): number {
  return Math.max(0, Math.ceil((expiresAtMs - nowMs) / 1000));
}

/** 「09:41」 - minutes and seconds, for the countdown. */
export function countdownText(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(whole / 60)).padStart(2, "0")}:${String(whole % 60).padStart(2, "0")}`;
}
