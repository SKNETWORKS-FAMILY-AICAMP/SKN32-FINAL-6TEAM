import type { Language } from "../i18n";
import { API_BASE, sessionInit } from "./client";

/**
 * The server's "this trip changed" bell (`GET /v1/web/trips/{id}/events`, text/event-stream).
 *
 * ★The bell carries no content — only which trip and roughly what changed. The screen re-reads the trip,
 *   its notices and its proposals with the GETs it already has. So a bell missed while the connection was
 *   down loses nothing: the database is the record, and a reconnect re-reads everything
 *   (2026-09-30 user decision — no replay of missed bells, no 30-second polling while the bell works).
 *
 * ★`EventSource` cannot send the `X-User-Key` header, and the key must not go in the URL. So the stream is read
 *   with fetch and the few lines of reconnecting live in `use-trip-events.ts`.
 */

export type ChangeKind = "itinerary" | "notice" | "proposal";
const KINDS: readonly ChangeKind[] = ["itinerary", "notice", "proposal"];

export type TripEvent =
  | { type: "ready"; version: number | null }
  | { type: "changed"; kinds: ChangeKind[]; version: number | null };

/** How a watch ended. `unsupported` — this server has no bell (404/405): the screen goes back to re-reading every 30 s. */
export type WatchEnd = "closed" | "unsupported" | "failed";

/** One server-sent event block → a trip event, or null for what the screen does not use. Unknown kinds mean "re-read all". */
export function toTripEvent(name: string, data: string): TripEvent | null {
  let body: { version?: unknown; kinds?: unknown } = {};
  try { body = data ? JSON.parse(data) as typeof body : {}; } catch { body = {}; }
  const version = typeof body.version === "number" ? body.version : null;
  if (name === "ready") return { type: "ready", version };
  if (name !== "trip.changed") return null;
  const listed = Array.isArray(body.kinds) ? body.kinds.filter((kind): kind is ChangeKind => KINDS.includes(kind as ChangeKind)) : [];
  return { type: "changed", kinds: listed.length ? listed : [...KINDS], version };
}

/**
 * Split a text/event-stream into events. Feed it chunks as they arrive; it keeps the unfinished tail.
 * Comment lines (`: ping`, the server's keep-the-line-open heartbeat) are dropped here.
 */
export function eventStreamParser(onEvent: (name: string, data: string) => void) {
  let buffer = "";
  let name = "";
  let data: string[] = [];
  return (chunk: string) => {
    buffer += chunk;
    const lines = buffer.split(/\r\n|\r|\n/);
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line === "") {
        if (data.length || name) onEvent(name || "message", data.join("\n"));
        name = ""; data = [];
      } else if (line.startsWith(":")) {
        continue;
      } else {
        const colon = line.indexOf(":");
        const field = colon === -1 ? line : line.slice(0, colon);
        const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
        if (field === "event") name = value;
        else if (field === "data") data.push(value);
      }
    }
  };
}

/** Open the bell for one trip and call `onEvent` until the stream ends or `signal` aborts. Never throws. */
export async function watchTrip(tripId: string, language: Language, onEvent: (event: TripEvent) => void, signal: AbortSignal): Promise<WatchEnd> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/v1/web/trips/${encodeURIComponent(tripId)}/events`, await sessionInit(language, {
      headers: { Accept: "text/event-stream" },
      cache: "no-store",
      signal,
    }));
  } catch {
    return signal.aborted ? "closed" : "failed";
  }
  if (response.status === 404 || response.status === 405) return "unsupported";
  if (!response.ok || !response.body) return "failed";
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  const feed = eventStreamParser((name, data) => {
    const event = toTripEvent(name, data);
    if (event) onEvent(event);
  });
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) return "closed";
      feed(value);
    }
  } catch {
    return signal.aborted ? "closed" : "failed";
  }
}
