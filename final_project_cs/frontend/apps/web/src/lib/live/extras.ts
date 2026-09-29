import type { Language } from "../i18n";
import { api, currentKey } from "./client";

/**
 * The rest of the server's web API: the choices the server is waiting for, the notices it sent,
 * and choosing. Everything here is what the server says — the screen adds no sentence of its own.
 */

export interface ProposalOption { key: string; rank: number | null; name: string; startsAt: string | null }

/** A change the server would like the customer to decide (`GET /v1/web/trips/{id}/proposals`). */
export interface Proposal {
  id: string;
  itemId: string;
  baseVersion: number;
  reason: string;
  status: string;
  safety: boolean;
  expiresAt: string | null;
  options: ProposalOption[];
}

interface ServerProposal {
  proposal_id: string; item_id: string; base_version: number; reason: string; status: string; safety?: unknown;
  expires_at?: string | null; options?: { key: string; rank?: number | null; name?: string | null; starts_at?: string | null }[];
}

export async function getProposals(tripId: string, language: Language): Promise<Proposal[]> {
  const body = await api<{ proposals?: ServerProposal[] }>(`/v1/web/trips/${encodeURIComponent(tripId)}/proposals`, language);
  return (body.proposals ?? []).map((row) => ({
    id: row.proposal_id, itemId: row.item_id, baseVersion: row.base_version, reason: row.reason, status: row.status,
    safety: Boolean(row.safety), expiresAt: row.expires_at ?? null,
    // ★An option without a name is dropped: there is nothing true to show for it.
    options: (row.options ?? []).filter((option) => option.name).map((option) => ({
      key: option.key, rank: option.rank ?? null, name: option.name as string, startsAt: option.starts_at ?? null,
    })),
  }));
}

export type NoticeType = "guidance" | "proposal_request" | "safety_alert" | "change_notice";

/** A notice the server sent about this trip (`GET /v1/web/trips/{id}/notices`). `text` is the server's sentence. */
export interface Notice {
  key: string;
  type: string;
  kind: string | null;
  text: string | null;
  version: number | null;
  proposalId: string | null;
  delivery: string;
  at: string;
}

interface ServerNotice {
  key: string; type?: string | null; kind?: string | null; text?: string | null; version?: number | null;
  proposal_id?: string | null; delivery: string; at: string;
}

export async function getNotices(tripId: string, language: Language): Promise<Notice[]> {
  const body = await api<{ notices?: ServerNotice[] }>(`/v1/web/trips/${encodeURIComponent(tripId)}/notices`, language);
  return (body.notices ?? []).map((row) => ({
    key: row.key, type: row.type ?? "change_notice", kind: row.kind ?? null, text: row.text ?? null,
    version: row.version ?? null, proposalId: row.proposal_id ?? null, delivery: row.delivery, at: row.at,
  }));
}

/**
 * Decide a proposal (`POST .../proposals/{id}/choose`). `key = null` keeps the current plan.
 * The server refuses with 409 `already_decided` / `stale` when someone (or a newer version) got there first —
 * those come back as a `LiveError` with the server's code.
 */
export function chooseProposal(tripId: string, proposalId: string, key: string | null, language: Language): Promise<{ status?: string }> {
  return api(`/v1/web/trips/${encodeURIComponent(tripId)}/proposals/${encodeURIComponent(proposalId)}/choose`, language, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ key }),
  });
}

/** What the server said about the chat model (`POST /v1/web/warmup`). `lastAttempt.ok === false` = the model server could not load it. */
export interface Warmup {
  status: string;
  model: string | null;
  lastAttempt: { ok: boolean; seconds: number | null; at: string | null; reason: string | null } | null;
  deduped: boolean;
}

/**
 * Wake the chat model before the customer asks — a cold model took about 35 s to answer the first message
 * (2026-09-29, measured). The server does nothing if it is already up and calls it at most once a minute.
 * ★Never issues a key: without a stored key there is no trip to chat about, and asking would create a user.
 */
export async function warmup(language: Language): Promise<Warmup | null> {
  if (!currentKey()) return null;
  const body = await api<{ status?: string; model?: string | null; deduped?: boolean;
    last_attempt?: { ok?: boolean; seconds?: number | null; at?: string | null; reason?: string | null } | null }>("/v1/web/warmup", language, { method: "POST" });
  const last = body.last_attempt;
  return {
    status: body.status ?? "unknown", model: body.model ?? null, deduped: body.deduped === true,
    lastAttempt: last ? { ok: last.ok === true, seconds: last.seconds ?? null, at: last.at ?? null, reason: last.reason ?? null } : null,
  };
}

/** The server's answer to "may this screen load Google Maps once?" (`POST /v1/web/map-load`). */
export interface MapLoad {
  allowed: boolean;
  /** Which map the operator set (`web.map_provider`, changed from the developer console). Unknown when the server did not say. */
  provider: "osm" | "google" | null;
  /** Why Google was refused: the operator chose the free map (`setting`), the cap was reached (`cap`), or no answer (`error`). */
  reason: "setting" | "cap" | "error" | null;
  used: { day: number | null; month: number | null };
  cap: { day: number | null; month: number | null };
}

/**
 * ★Ask before every Google map load — Google bills each load, and the server counts them for all users together
 * (cap 312/day, 9,688/month, 2026-09-29). No key, no answer, or any failure means "not allowed": the screen shows
 * the free map instead of calling Google unchecked.
 */
export async function mapLoad(language: Language): Promise<MapLoad> {
  const denied: MapLoad = { allowed: false, provider: null, reason: "error", used: { day: null, month: null }, cap: { day: null, month: null } };
  if (!currentKey()) return denied;
  try {
    const body = await api<{ allowed?: unknown; provider?: unknown; reason?: unknown; used?: { day?: number; month?: number }; cap?: { day?: number; month?: number } }>(
      "/v1/web/map-load", language, { method: "POST" });
    const provider = body.provider === "osm" || body.provider === "google" ? body.provider : null;
    const allowed = body.allowed === true && provider !== "osm";
    return {
      allowed,
      provider,
      // ★An older server says only `allowed`; a refusal without a reason is treated as the cap (the one refusal it knew).
      reason: allowed ? null : body.reason === "setting" || provider === "osm" ? "setting" : "cap",
      used: { day: body.used?.day ?? null, month: body.used?.month ?? null },
      cap: { day: body.cap?.day ?? null, month: body.cap?.month ?? null },
    };
  } catch {
    return denied;
  }
}
