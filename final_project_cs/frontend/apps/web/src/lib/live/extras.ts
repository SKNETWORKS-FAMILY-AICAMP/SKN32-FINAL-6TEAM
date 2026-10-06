import type { Language } from "../i18n";
import { api, hasSession } from "./client";

/**
 * The rest of the server's web API: the choices the server is waiting for, the notices it sent,
 * and choosing. Everything here is what the server says — the screen adds no sentence of its own.
 */

/** `note` — how this option bends what the customer asked for (「09:00으로 늦추면」 · 「다음 일정(경복궁) 근처」), in the server's words. */
export interface ProposalOption {
  key: string; rank: number | null; name: string; startsAt: string | null; note: string | null;
  /** What the server could not confirm about this option (「그 시각 영업을 확인할 수 없다」), in its own words. */
  warnings: string[];
}

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
  expires_at?: string | null; options?: { key: string; rank?: number | null; name?: string | null; starts_at?: string | null; note?: string | null; warnings?: unknown[] | null }[];
}

export async function getProposals(tripId: string, language: Language): Promise<Proposal[]> {
  const body = await api<{ proposals?: ServerProposal[] }>(`/v1/web/trips/${encodeURIComponent(tripId)}/proposals`, language);
  return (body.proposals ?? []).map((row) => ({
    id: row.proposal_id, itemId: row.item_id, baseVersion: row.base_version, reason: row.reason, status: row.status,
    safety: Boolean(row.safety), expiresAt: row.expires_at ?? null,
    // ★An option without a name is dropped: there is nothing true to show for it.
    options: (row.options ?? []).filter((option) => option.name).map((option) => ({
      key: option.key, rank: option.rank ?? null, name: option.name as string, startsAt: option.starts_at ?? null,
      note: typeof option.note === "string" && option.note.trim() ? option.note.trim() : null,
      warnings: (option.warnings ?? []).filter((warning): warning is string => typeof warning === "string" && warning.trim() !== ""),
    })),
  }));
}

export type NoticeType = "guidance" | "proposal_request" | "safety_alert" | "change_notice";

/** One place to go to in a disaster (`guidance.shelters[]` of a safety alert): the server's own row, with a walking-directions link when it has one. */
export interface Shelter {
  name: string;
  address: string | null;
  /** Straight-line metres from the planned place. */
  distanceM: number | null;
  /** An ESTIMATE (4 km/h along the straight line), not a measured route. */
  walkMinutes: number | null;
  underground: boolean | null;
  capacity: number | null;
  /** A link that opens walking directions (https only). */
  mapUrl: string | null;
}

/**
 * `[2026-10-06]` The guidance of a safety alert (`safety` of a notice, rest-endpoints 「재난 시 일정 정지」). ★The reference point is the PLACE IN THE PLAN, not where the customer is: `reference.note`
 * says so in the server's words and the screen shows it with the list. `shelterStatus`: ok · none_nearby · no_data (the shelter table is empty: official guidance only) · no_reference_place · not_applicable.
 */
export interface SafetyGuidance {
  level: string | null;
  /** `upcoming`: the trip has not started - there is no shelter list, only the official guidance to check the local situation before going. */
  phase: "in_progress" | "upcoming" | null;
  label: string | null;
  official: { source: string | null; text: string | null; at: string | null } | null;
  /** A phone number to call in danger ("119"), digits only. */
  emergencyCall: string | null;
  /** The portal to follow first (「국민재난안전포털」), by name. */
  portal: string | null;
  reference: { place: string | null; note: string | null } | null;
  shelters: Shelter[];
  shelterStatus: string | null;
}

const str = (value: unknown): string | null => (typeof value === "string" && value.trim() ? value.trim() : null);
const num = (value: unknown): number | null => (typeof value === "number" && Number.isFinite(value) ? value : null);

/** A server `safety` guidance of a notice. Not an object: null. A shelter without a name is dropped (nothing true to show for it). */
export function guidanceOf(raw: unknown): SafetyGuidance | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  const official = row.official && typeof row.official === "object" ? row.official as Record<string, unknown> : null;
  const reference = row.reference && typeof row.reference === "object" ? row.reference as Record<string, unknown> : null;
  const call = str(row.emergency_call);
  return {
    level: str(row.level), phase: row.phase === "in_progress" || row.phase === "upcoming" ? row.phase : null, label: str(row.label),
    official: official ? { source: str(official.source), text: str(official.text), at: str(official.at) } : null,
    emergencyCall: call && /^\d{2,4}$/.test(call) ? call : null,
    portal: str(row.portal),
    reference: reference ? { place: str(reference.place), note: str(reference.note) } : null,
    shelters: (Array.isArray(row.shelters) ? row.shelters : []).flatMap((entry): Shelter[] => {
      if (!entry || typeof entry !== "object") return [];
      const shelter = entry as Record<string, unknown>;
      const name = str(shelter.name);
      const link = str(shelter.map_url);
      return name ? [{
        name, address: str(shelter.address), distanceM: num(shelter.distance_m), walkMinutes: num(shelter.walk_minutes_estimate),
        underground: typeof shelter.underground === "boolean" ? shelter.underground : null, capacity: num(shelter.capacity),
        mapUrl: link && link.startsWith("https://") ? link : null,
      }] : [];
    }),
    shelterStatus: str(row.shelter_status),
  };
}

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
  /** An automatic change the customer can undo from this notice (the server attaches it only when it changed the plan on its own). */
  rollback: { baseVersion: number; toVersion: number; requestId: string } | null;
  /** `[2026-10-06]` A safety alert's guidance (what to follow, where to go); null on any other notice. */
  safety: SafetyGuidance | null;
}

interface ServerNotice {
  key: string; type?: string | null; kind?: string | null; text?: string | null; version?: number | null;
  proposal_id?: string | null; delivery: string; at: string;
  rollback?: { base_version?: unknown; to_version?: unknown; request_id?: unknown } | null;
  safety?: unknown;
}

function rollbackOf(raw: ServerNotice["rollback"]): Notice["rollback"] {
  if (!raw || typeof raw !== "object") return null;
  const { base_version: base, to_version: to, request_id: id } = raw;
  return typeof base === "number" && typeof to === "number" && typeof id === "string" && id ? { baseVersion: base, toVersion: to, requestId: id } : null;
}

export async function getNotices(tripId: string, language: Language): Promise<Notice[]> {
  const body = await api<{ notices?: ServerNotice[] }>(`/v1/web/trips/${encodeURIComponent(tripId)}/notices`, language);
  return (body.notices ?? []).map((row) => ({
    key: row.key, type: row.type ?? "change_notice", kind: row.kind ?? null, text: row.text ?? null,
    version: row.version ?? null, proposalId: row.proposal_id ?? null, delivery: row.delivery, at: row.at,
    rollback: rollbackOf(row.rollback),
    safety: guidanceOf(row.safety),
  }));
}

/**
 * `[2026-10-06]` 「일정 다시 시작」 (`POST /v1/web/trips/{id}/safety/resume`, no body): the customer says they are safe and the pause is lifted. ★Only the customer's press does it - the server cannot know
 * they are safe, so nothing resumes by itself. The plan was never changed by the pause. `resumed` = how many pauses were closed (0 when there was none - not an error).
 */
export async function resumeSafety(tripId: string, language: Language): Promise<{ resumed: number }> {
  const body = await api<{ resumed?: unknown }>(`/v1/web/trips/${encodeURIComponent(tripId)}/safety/resume`, language, { method: "POST" });
  return { resumed: typeof body.resumed === "number" ? body.resumed : 0 };
}

/** Where the Course Keeper was turned on or off from (`via` of `POST /v1/web/trips/{id}/guardian`; the server records it). */
export type GuardianVia = "card" | "header" | "notice" | "settings";

/**
 * `[2026-10-06 사용자 결정]` Turn the Course Keeper of a REGISTERED trip on or off (`POST /v1/web/trips/{id}/guardian`) -> `{enabled, since, via}`. Only a cookie session may call it (an agent key or a plan
 * link cannot: automatic changes are a right to change the plan); the same value again changes nothing and returns the present state. A failure is a `LiveError` - the state stays as it was.
 */
export async function setGuardian(tripId: string, enabled: boolean, via: GuardianVia, language: Language): Promise<{ enabled: boolean; since: string | null; via: string | null }> {
  const body = await api<{ enabled?: unknown; since?: unknown; via?: unknown }>(`/v1/web/trips/${encodeURIComponent(tripId)}/guardian`, language, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled, via }),
  });
  return { enabled: body.enabled === true, since: typeof body.since === "string" ? body.since : null, via: typeof body.via === "string" ? body.via : null };
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
 * ★Never makes a session: without one there is no trip to chat about, and asking would create a user.
 */
export async function warmup(language: Language): Promise<Warmup | null> {
  if (!await hasSession(language)) return null;
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
  try {
    if (!await hasSession(language)) return denied;
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

/**
 * Undo an automatic change (`POST /v1/web/trips/{id}/rollback`). The server answers 409 when the trip has already moved
 * to another version — that comes back as a `LiveError`; nothing changed. The same `requestId` sent twice is one undo.
 */
export function undoChange(tripId: string, rollback: NonNullable<Notice["rollback"]>, language: Language): Promise<{ status?: string; answer?: string }> {
  return api(`/v1/web/trips/${encodeURIComponent(tripId)}/rollback`, language, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ request_id: rollback.requestId, base_version: rollback.baseVersion, to_version: rollback.toVersion }),
  });
}
