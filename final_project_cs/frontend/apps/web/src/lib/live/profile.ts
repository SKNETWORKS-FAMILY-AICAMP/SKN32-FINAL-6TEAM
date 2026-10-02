import type { Language } from "../i18n";
import { api, LiveError } from "./client";

/**
 * The customer's contact details on the server (`GET/PUT /v1/web/profile`, 2026-10-01).
 *
 * ★The Discord webhook is a secret the server will use to send: the server never returns it, only a masked form and
 *   whether it works. This screen layer keeps none of it — there is no webhook field yet, the types are here so the
 *   field can be added without touching the transport.
 */
export interface ServerProfile {
  recoveryEmail: string | null;
  webhook: { set: boolean; masked: string | null; status: "untested" | "ok" | "invalid" | null; checkedAt: string | null };
  updatedAt: string | null;
}

interface Wire {
  recovery_email?: string | null;
  discord_webhook?: { set?: boolean; masked?: string | null; status?: string | null; checked_at?: string | null } | null;
  updated_at?: string | null;
}

const STATUSES = ["untested", "ok", "invalid"] as const;

function read(wire: Wire): ServerProfile {
  const hook = wire.discord_webhook ?? {};
  const status = STATUSES.find((value) => value === hook.status) ?? null;
  return {
    recoveryEmail: typeof wire.recovery_email === "string" && wire.recovery_email.trim() ? wire.recovery_email.trim() : null,
    webhook: { set: hook.set === true, masked: typeof hook.masked === "string" ? hook.masked : null, status, checkedAt: hook.checked_at ?? null },
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

/** Partial update: a field left out is not touched; `null` removes it. */
export async function putProfile(patch: { recoveryEmail?: string | null }, language: Language): Promise<ServerProfile> {
  const body: Record<string, unknown> = {};
  if ("recoveryEmail" in patch) body.recovery_email = patch.recoveryEmail;
  return read(await api<Wire>("/v1/web/profile", language, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }));
}
