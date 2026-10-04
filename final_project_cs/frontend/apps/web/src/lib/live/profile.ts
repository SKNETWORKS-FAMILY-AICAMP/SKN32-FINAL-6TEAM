import type { Language } from "../i18n";
import { api, LiveError } from "./client";

/**
 * The customer's contact details on the server (`GET/PUT /v1/web/profile`, `POST …/discord/test`, 2026-10-01).
 *
 * ★The Discord webhook is a secret the server will use to send: the server never returns it, only a masked form and
 *   whether it works. The web sends it once (`lib/webhook.ts`) and keeps none of it.
 */
export interface ServerProfile {
  webhook: { set: boolean; masked: string | null; status: "untested" | "ok" | "invalid" | null; checkedAt: string | null };
  /** `[2026-10-05]` The server can connect a Discord channel through Discord's own window (`discord_connect.available`); an older server does not say, so false. */
  discordConnect: boolean;
  updatedAt: string | null;
}

interface Wire {
  discord_webhook?: { set?: boolean; masked?: string | null; status?: string | null; checked_at?: string | null } | null;
  discord_connect?: { available?: boolean } | null;
  updated_at?: string | null;
}

const STATUSES = ["untested", "ok", "invalid"] as const;

function read(wire: Wire): ServerProfile {
  const hook = wire.discord_webhook ?? {};
  const status = STATUSES.find((value) => value === hook.status) ?? null;
  return {
    webhook: { set: hook.set === true, masked: typeof hook.masked === "string" ? hook.masked : null, status, checkedAt: hook.checked_at ?? null },
    discordConnect: wire.discord_connect?.available === true,
    updatedAt: wire.updated_at ?? null,
  };
}

/** A server without this call answers 404/405 — the caller then keeps the value in this browser only. */
export function isUnsupported(error: unknown): boolean {
  return error instanceof LiveError && ["not_found", "method_not_allowed", "HTTP_404", "HTTP_405"].includes(error.code);
}

export async function getProfile(language: Language): Promise<ServerProfile> {
  return read(await api<Wire>("/v1/web/profile", language));
}

/** Partial update: a field left out is not touched; `null` removes it. One wrong value refuses the whole update (422). */
export async function putProfile(patch: { discordWebhookUrl?: string | null }, language: Language): Promise<ServerProfile> {
  const body: Record<string, unknown> = {};
  if ("discordWebhookUrl" in patch) body.discord_webhook_url = patch.discordWebhookUrl;
  return read(await api<Wire>("/v1/web/profile", language, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }));
}

/** How a test message went: sent (`ok`), Discord refused the webhook (`invalid` — gone or wrong), Discord limited us, or it failed. */
export type WebhookTestResult = "ok" | "invalid" | "rate_limited" | "failed";
const RESULTS = ["ok", "invalid", "rate_limited", "failed"] as const;

/**
 * Send one test line through the saved webhook — only when the customer presses it. 409 `no_webhook` / `unreadable`
 * and 429 `too_soon` (with when to try again) come back as errors.
 */
export async function testDiscordWebhook(language: Language): Promise<{ result: WebhookTestResult; profile: ServerProfile }> {
  const answer = await api<{ result?: string; profile?: Wire }>("/v1/web/profile/discord/test", language, { method: "POST" });
  return { result: RESULTS.find((value) => value === answer.result) ?? "failed", profile: read(answer.profile ?? {}) };
}
