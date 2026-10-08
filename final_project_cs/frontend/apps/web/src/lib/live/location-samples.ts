import type { Language } from "../i18n";
import { distanceM, type LocationFix } from "../location";
import { api, LiveError } from "./client";

/**
 * `[2026-10-05 사용자 지시]` 「서버에서 고객이 정확히 어느 지점에서 멈춘 건지 체크」 — the web's part: hand the server the positions the trip's map already
 * reads, so the server can find where the customer stayed, and read back what it found. The server does the finding (radius, minutes, matching a stop of
 * the plan); the page works nothing out. Contract: `wiki/records/plans/2026-10-05_동의기록_위치수집_백엔드_요청.md` §2 · §3.
 *
 *   POST   /v1/web/trips/{trip_id}/location        {"fixes": [{lat, lng, accuracy_m?, at}]} — at most 20 a call → {saved, skipped}
 *   DELETE /v1/web/trips/{trip_id}/location        every point and stay of this trip → {deleted}
 *   GET    /v1/web/trips/{trip_id}/location/stops  {stops: [...], last_fix, computed_at}
 *
 * Rules on the page:
 * - ★Only with the customer's location consent, and only from a trip's own screen (a trip id — the plan check has none, so it sends nothing).
 * - A point is kept when the customer moved ≥ 30 m from the last one kept, or 60 s passed; the same fix (`at`) is never kept twice.
 * - Kept points go together every 60 s, and when the page is hidden or the screen closes.
 * - 403 `consent_required` → stop for good. The page reads the consent again: `api` fires `CONSENT_REQUIRED_EVENT` on that answer and the consent
 *   gate re-reads the server's record (a location consent withdrawn elsewhere then turns the map's following off). 404/405 (a server without these
 *   routes) → stop quietly, nothing on screen; no answer / 5xx / 429 → try again next time.
 * - ★Points live in memory only — never browser storage, the console, an error message or a URL.
 */
export const SAMPLE_MOVE_M = 30;
export const SAMPLE_EVERY_MS = 60_000;
export const SEND_EVERY_MS = 60_000;
export const FIXES_PER_CALL = 20;
/** Calls in one send at most: the server allows six a minute for a user, and a backlog goes over the next sends. */
export const CALLS_PER_SEND = 3;
/** Points held while the server cannot be reached; past this the oldest go (two hours at one a minute). */
export const QUEUE_LIMIT = 120;

/** One point as the server takes it. */
export interface LocationSampleWire { lat: number; lng: number; accuracy_m?: number; at: string }

/** `running` — keeps and sends; anything else — stopped for good (a new sampler starts again). */
export type SamplerState = "running" | "consent_required" | "unsupported" | "ended" | "stopped";
export type FlushResult = "sent" | "nothing" | "retry" | "stopped";

export interface LocationSampler {
  /** Keep this fix if it is worth sending (moved 30 m, or 60 s later, and not seen before). True when kept. */
  add(fix: LocationFix): boolean;
  /** Send what is kept now. */
  flush(): Promise<FlushResult>;
  /** Stop for good and forget what is kept (the screen closed, or the consent was withdrawn). */
  stop(): void;
  readonly state: SamplerState;
  /** How many points wait to be sent. */
  readonly pending: number;
}

const finite = (value: number) => typeof value === "number" && Number.isFinite(value);

export function wireOf(fix: LocationFix): LocationSampleWire {
  return { lat: fix.lat, lng: fix.lng, ...(fix.accuracyM !== null && finite(fix.accuracyM) ? { accuracy_m: fix.accuracyM } : {}), at: fix.at };
}

/** What a refusal means for the sending. */
export function outcomeOf(error: unknown): "retry" | "drop" | Exclude<SamplerState, "running" | "stopped"> {
  if (!(error instanceof LiveError)) return "retry";
  const code = error.code;
  if (code === "consent_required") return "consent_required";
  // A server without these routes yet (FastAPI 404/405), or no such trip for this customer: nothing to send to.
  if (["not_found", "method_not_allowed", "HTTP_404", "HTTP_405"].includes(code)) return "unsupported";
  // The session ended (sending again would make a NEW guest — `api` never does that silently, and neither do we), or the trip is not this customer's.
  if (["session_expired", "unauthenticated", "forbidden", "HTTP_403"].includes(code)) return "ended";
  // The server will never take these points: drop them rather than send them every minute.
  if (["HTTP_400", "HTTP_422", "validation_error"].includes(code) || code.startsWith("invalid_")) return "drop";
  return "retry";                                         // network, timeout, 5xx, 429 (`rate_limited` …), a CSRF token read again …
}

type Post = (fixes: LocationSampleWire[]) => Promise<unknown>;

/**
 * The sender for one trip. `post` is the call (tests give their own); `onConsentRequired` is called once when the server says the consent is missing.
 * ★No `keepalive` on the call: it would need a CORS preflight (JSON + the CSRF header, another origin), which not every browser allows for it. A hidden
 *   page still runs, so the send goes through; a page closed mid-send loses at most a minute of points.
 */
export function createLocationSampler(tripId: string, options: { language?: Language; post?: Post; onConsentRequired?: () => void } = {}): LocationSampler {
  const language = options.language ?? "ko";
  const post: Post = options.post ?? ((fixes) => api(`/v1/web/trips/${encodeURIComponent(tripId)}/location`, language, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ fixes }),
  }));
  let state: SamplerState = "running";
  let queue: LocationSampleWire[] = [];
  let kept: LocationFix | null = null;
  let sending: Promise<FlushResult> | null = null;

  function halt(next: Exclude<SamplerState, "running">) {
    if (state !== "running") return;
    state = next;
    queue = [];
    if (next === "consent_required") options.onConsentRequired?.();
  }

  async function send(): Promise<FlushResult> {
    for (let call = 0; call < CALLS_PER_SEND && queue.length && state === "running"; call += 1) {
      const batch = queue.slice(0, FIXES_PER_CALL);
      const done = () => { const sent = new Set(batch); queue = queue.filter((item) => !sent.has(item)); };
      try {
        await post(batch);
      } catch (error) {
        const outcome = outcomeOf(error);
        if (outcome === "drop") { done(); continue; }
        if (outcome === "retry") return state === "running" ? "retry" : "stopped";
        halt(outcome);
        return "stopped";
      }
      done();
    }
    return state === "running" ? "sent" : "stopped";
  }

  return {
    add(fix) {
      if (state !== "running" || !finite(fix.lat) || !finite(fix.lng) || Math.abs(fix.lat) > 90 || Math.abs(fix.lng) > 180) return false;
      const at = Date.parse(fix.at);
      if (!Number.isFinite(at)) return false;
      if (kept) {
        const keptAt = Date.parse(kept.at);
        if (at <= keptAt) return false;                     // the same fix again (a cached answer), or an older one
        if (distanceM(kept, fix) < SAMPLE_MOVE_M && at - keptAt < SAMPLE_EVERY_MS) return false;
      }
      kept = fix;
      queue.push(wireOf(fix));
      if (queue.length > QUEUE_LIMIT && !sending) queue = queue.slice(queue.length - QUEUE_LIMIT);
      return true;
    },
    flush() {
      if (state !== "running") return Promise.resolve("stopped");
      if (sending) return sending;
      if (!queue.length) return Promise.resolve("nothing");
      sending = send().finally(() => { sending = null; });
      return sending;
    },
    stop() { halt("stopped"); },
    get state() { return state; },
    get pending() { return queue.length; },
  };
}

/** Delete every point and stay of this trip on the server (the location consent was withdrawn). `null` — a server without the route (nothing was kept there). */
export async function deleteLocationSamples(tripId: string, language: Language = "ko"): Promise<{ deleted: number } | null> {
  try {
    const body = await api<{ deleted?: unknown }>(`/v1/web/trips/${encodeURIComponent(tripId)}/location`, language, { method: "DELETE" });
    const deleted = Number(body?.deleted);
    return { deleted: Number.isInteger(deleted) && deleted >= 0 ? deleted : 0 };
  } catch (error) {
    if (outcomeOf(error) === "unsupported") return null;
    throw error;
  }
}

// ── where the customer stayed, as the server found it ───────────────────────────────────────────

export interface LocationStay {
  stopId: string;
  lat: number;
  lng: number;
  startedAt: string;
  /** null — still there (the server says so). */
  endedAt: string | null;
  radiusM: number | null;
  points: number | null;
  /** The stop of the plan it is near (within 100 m, the server decides); null — a place not in the plan. */
  matchedItemId: string | null;
}

export interface LocationStops {
  stops: LocationStay[];
  lastFix: { lat: number; lng: number; at: string; accuracyM: number | null } | null;
  computedAt: string | null;
}

const text = (value: unknown): string | null => (typeof value === "string" && value.trim() ? value : null);
const number = (value: unknown): number | null => (typeof value === "number" && Number.isFinite(value) ? value : null);
const lat = (value: unknown) => { const n = number(value); return n !== null && n >= -90 && n <= 90 ? n : null; };
const lng = (value: unknown) => { const n = number(value); return n !== null && n >= -180 && n <= 180 ? n : null; };
const time = (value: unknown) => { const t = text(value); return t && Number.isFinite(Date.parse(t)) ? t : null; };

function stayOf(entry: unknown): LocationStay | null {
  const row = (entry ?? {}) as Record<string, unknown>;
  const stopId = text(row.stop_id), at = lat(row.lat), on = lng(row.lng), startedAt = time(row.started_at);
  if (!stopId || at === null || on === null || !startedAt) return null;           // nothing to draw is drawn — never a guess
  const radius = number(row.radius_m), points = number(row.points);
  return {
    stopId, lat: at, lng: on, startedAt, endedAt: time(row.ended_at),
    radiusM: radius !== null && radius >= 0 ? radius : null, points: points !== null && points >= 0 ? Math.round(points) : null,
    matchedItemId: text(row.matched_item_id),
  };
}

/** The server's answer → what the map can draw. A stay without an id, a place or a start is left out; an answer that is not one has no stays. Pure. */
export function readLocationStops(body: unknown): LocationStops {
  const data = (body ?? {}) as { stops?: unknown; last_fix?: unknown; computed_at?: unknown };
  const stops = (Array.isArray(data.stops) ? data.stops : []).map(stayOf).filter((stay): stay is LocationStay => stay !== null);
  const fix = (data.last_fix ?? null) as Record<string, unknown> | null;
  const fixLat = fix ? lat(fix.lat) : null, fixLng = fix ? lng(fix.lng) : null, fixAt = fix ? time(fix.at) : null;
  const accuracy = fix ? number(fix.accuracy_m) : null;
  return {
    stops,
    lastFix: fixLat !== null && fixLng !== null && fixAt ? { lat: fixLat, lng: fixLng, at: fixAt, accuracyM: accuracy !== null && accuracy >= 0 ? accuracy : null } : null,
    computedAt: time(data.computed_at),
  };
}

/** Where the server found the customer stayed on this trip. `null` — a server without the route (an older one): nothing to draw, and no error to show. */
export async function getLocationStops(tripId: string, language: Language = "ko"): Promise<LocationStops | null> {
  try {
    return readLocationStops(await api<unknown>(`/v1/web/trips/${encodeURIComponent(tripId)}/location/stops`, language));
  } catch (error) {
    if (outcomeOf(error) === "unsupported") return null;
    throw error;
  }
}
