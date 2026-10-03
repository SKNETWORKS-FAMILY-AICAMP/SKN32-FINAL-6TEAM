"use client";

import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { nextStep, STAGES, type CheckRow, type PlanCheckView, type Verdict } from "./model";

/** The longest pause between two drawn changes — slow enough to follow a small plan. */
export const REVEAL_MS = 280;
/**
 * ★`[2026-10-03]` A big plan is not drawn at that pace: the real server sends every check of a 14-stop plan at once, and
 * 200-odd changes at 280 ms kept the screen a minute behind the server. The pause shrinks so that what is waiting is drawn
 * in about this long — measured against the most that has been waiting (the pause stays the same as the backlog falls, so
 * the whole takes the budget, not the budget times a harmonic sum) — but never below `REVEAL_MIN_MS` (each change must still be seen).
 */
export const REVEAL_BUDGET_MS = 8_000;
export const REVEAL_MIN_MS = 35;

/** About how many drawn changes lie between `shown` and `target`: a line read, a place or leg appearing, each of its checks, its verdict, a stage. */
export function backlog(shown: PlanCheckView, target: PlanCheckView): number {
  const pending = <T extends { id: string; checks: CheckRow[]; verdict: Verdict | null }>(have: T[], want: T[]) => want.reduce((sum, entity) => {
    const seen = have.find((other) => other.id === entity.id);
    if (!seen) return sum + 2 + entity.checks.length;
    return sum + entity.checks.filter((row, at) => JSON.stringify(row) !== JSON.stringify(seen.checks[at])).length + (seen.verdict === entity.verdict ? 0 : 1);
  }, 0);
  const lines = target.lines.reduce((sum, line, at) => {
    const seen = shown.lines[at];
    return sum + (seen ? (!seen.read && line.read ? 1 : 0) : line.read ? 2 : 1);
  }, 0);
  return lines + pending(shown.items, target.items) + pending(shown.moves, target.moves) + Math.max(0, STAGES.indexOf(target.stage) - STAGES.indexOf(shown.stage));
}

/** The pause before the next drawn change: `max`, or shorter when a lot is waiting to be drawn (`waiting` = the most that has been waiting). */
export function revealPause(waiting: number, max = REVEAL_MS): number {
  return Math.min(max, Math.max(REVEAL_MIN_MS, Math.round(REVEAL_BUDGET_MS / Math.max(1, waiting))));
}

const QUERY = "(prefers-reduced-motion: reduce)";
function subscribe(onChange: () => void) {
  const media = matchMedia(QUERY);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
}

/**
 * The snapshot to draw, and whether it has caught up with `target`. The first snapshot is drawn as it is (a reload or a
 * late open shows where things stand, without replaying); every later one is reached one change at a time (`nextStep`).
 * With reduced motion it is drawn at once.
 */
export function useReveal(target: PlanCheckView, pause = REVEAL_MS): { view: PlanCheckView; settled: boolean } {
  const reduced = useSyncExternalStore(subscribe, () => matchMedia(QUERY).matches, () => false);
  const [shown, setShown] = useState(target);
  // The most that has been waiting since the screen last caught up: the pace is set by that, not by what is left.
  const peak = useRef(0);
  useEffect(() => {
    if (reduced) return;
    const next = nextStep(shown, target);
    if (!next) { peak.current = 0; return; }
    peak.current = Math.max(peak.current, backlog(shown, target));
    const timer = setTimeout(() => setShown(next), revealPause(peak.current, pause));
    return () => clearTimeout(timer);
  }, [shown, target, reduced, pause]);
  // ★The server's own count is not replayed: it is shown as it arrives, whatever row the drawing has got to (the rows follow at their pace).
  const live = useMemo(() => (shown.serverProgress === target.serverProgress ? shown : { ...shown, serverProgress: target.serverProgress }), [shown, target.serverProgress]);
  return reduced ? { view: target, settled: true } : { view: live, settled: nextStep(shown, target) === null };
}
