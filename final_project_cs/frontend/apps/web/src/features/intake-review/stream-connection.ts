import type { WatchEnd } from "@/lib/live/events";

/**
 * How the screen is hearing about the reading:
 * - `connecting` — opening the stream, nothing heard yet
 * - `live` — events are arriving; the screen needs no polling
 * - `lost` — the line went quiet (no event, not even the 3-second heartbeat, for 6 s) or dropped; reconnecting, and the
 *   screen reads the plan by polling meanwhile so it never freezes ("서버가 멈추면 사용자가 상태를 모른다")
 * - `polling` — this server has no stream (404/405), or it kept failing to open; the screen polls (and still retries)
 * - `closed` — the reading ended (result) or the screen is done with it
 */
export type StreamConnection = "connecting" | "live" | "lost" | "polling" | "closed";

/** No event for this long = the server or the line is dead: the heartbeat comes every 3 s, so two missed. */
export const SILENT_AFTER_MS = 6_000;
/** After this many openings in a row that did not deliver anything, stop calling it "reconnecting" — it is polling. */
export const FAILURES_BEFORE_POLLING = 3;

export type StreamSignal =
  | { kind: "heard" }
  | { kind: "silent"; ms: number }
  | { kind: "ended"; end: WatchEnd; failures: number };

/** The state after one thing happened. `closed` stays closed — only the hook ends it. */
export function connectionAfter(current: StreamConnection, signal: StreamSignal): StreamConnection {
  if (current === "closed") return current;
  switch (signal.kind) {
    case "heard": return "live";
    // Only a stream that was supposed to be carrying the reading can go quiet; a screen already polling stays polling.
    case "silent": return signal.ms >= SILENT_AFTER_MS && (current === "live" || current === "connecting") ? "lost" : current;
    case "ended": return signal.end === "unsupported" || signal.failures >= FAILURES_BEFORE_POLLING ? "polling" : "lost";
  }
}

/** Polling is on whenever the stream is not carrying the reading. */
export const needsPolling = (connection: StreamConnection) => connection !== "live" && connection !== "closed";
