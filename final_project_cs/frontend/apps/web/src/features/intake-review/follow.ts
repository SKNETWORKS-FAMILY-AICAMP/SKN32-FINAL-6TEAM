import type { IntakeWatchEvent } from "@/lib/live/stream";
import type { IntakeFollow } from "./use-intake-events";

/**
 * ★우리가 고른 값 — how often a beat that says nothing new still re-reads the intake while the server reads: five server beats (3 s each).
 * What only the GET carries (the questions' second list, which the server works out when a GET comes after its reading agent is done —
 * web-intakes 「두 번에 정한다」) reaches the screen at most this late. 10 minutes of reading are then at most 40 GETs from beats, not 200.
 */
export const BEAT_REREAD_MS = 15_000;

/**
 * `[2026-10-27]` When an event of the reading stream sends the screen to read the intake again (`GET …/trip-intakes/{id}`): a connection's first packet
 * (a reconnect replays the state, something may have been missed), a stage event (sent only on a change), a beat that names a new stage, the end — and a
 * beat once `BEAT_REREAD_MS` has passed since the last re-read. Beats carry no read values (web-intakes 「접수 읽기 진행」) and what the reading adds comes as
 * content events. ☆Before, every beat was a GET (x600, 2026-10-26: 110 GETs in 10 minutes for one intake while the server was jammed; the GET also works out
 * and stores the questions' plan, a write on the intake row the reader is writing).
 */
export function rereadGate(now: () => number = () => performance.now()): (event: IntakeWatchEvent) => boolean {
  let last: number | null = null;
  let stage: string | null = null;
  return (event) => {
    const at = now();
    const changed = event.type === "done" || last === null || event.kind !== "beat" || event.stage !== stage || at - last >= BEAT_REREAD_MS;
    if (event.type === "progress") stage = event.stage;
    if (changed) last = at;
    return changed;
  };
}

/** The intake is asked for on a timer only while there is no live stream (none here, or it went silent and reconnects) — not for the rest of the reading once it was lost. */
export const followPolls = (follow: IntakeFollow): boolean => follow === "polling" || follow === "lost";
