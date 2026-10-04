import type { Language } from "../i18n";
import { api, LiveError } from "./client";

/**
 * `[2026-10-05 사용자 지시]` 「디스코드로 연결」 — the customer picks the server and channel in Discord's own window instead of making a webhook and
 * pasting its address. Discord's OAuth2 `webhook.incoming` hands the webhook to OUR SERVER (never to this page), and the server keeps it the same way
 * as a pasted one (`PUT /v1/web/profile` `discord_webhook_url`: checked, encrypted, shown only masked). This file is the web's half of the contract
 * (`wiki/records/plans/2026-10-05_디스코드_연결버튼_백엔드_요청.md`):
 *   - `POST /v1/web/profile/discord/connect/start` (session) → `{ authorize_url }`; the browser then goes to Discord and back to the server's callback;
 *   - the server sends the browser to `{web}/mypage?discord=connected|cancelled|expired|failed` (`readDiscordReturn`).
 * ★Whether the button exists is the server's word (`GET /v1/web/profile` → `discord_connect.available`): an older server, or one with no Discord app set up,
 *   shows no button — nothing is faked.
 */

/** Where the server's callback sends the browser back: connected, the customer cancelled in Discord, the start went stale, or anything else went wrong. */
export type DiscordReturn = "connected" | "cancelled" | "expired" | "failed";

/** `?discord=…` of My page after the trip to Discord. Absent = this is not a return (null); a word we do not know counts as a failure. */
export function readDiscordReturn(search: string): DiscordReturn | null {
  const value = new URLSearchParams(search).get("discord");
  if (value === null) return null;
  return value === "connected" || value === "cancelled" || value === "expired" ? value : "failed";
}

/**
 * Where this browser may be sent to connect: Discord's own site. A development server may use a loopback address (the tests' mock of Discord's page);
 * anything else - a server that hands out some other address - is refused rather than followed.
 */
export function discordAddressOk(address: string): boolean {
  try {
    const url = new URL(address);
    if (url.protocol === "https:") return url.hostname === "discord.com" || url.hostname.endsWith(".discord.com");
    return url.protocol === "http:" && ["127.0.0.1", "localhost", "[::1]"].includes(url.hostname);
  } catch {
    return false;
  }
}

/** Ask the server for the address of Discord's window. Rejects when the server gives none (or gives an address that is not Discord's). */
export async function startDiscordConnect(language: Language): Promise<string> {
  const answer = await api<{ authorize_url?: unknown }>("/v1/web/profile/discord/connect/start", language, { method: "POST" });
  const address = typeof answer.authorize_url === "string" ? answer.authorize_url : "";
  if (!discordAddressOk(address)) throw new LiveError("bad_authorize_url", "서버가 디스코드 연결 주소를 주지 않았어요.");
  return address;
}
