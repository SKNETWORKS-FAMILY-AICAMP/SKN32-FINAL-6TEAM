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
export const REVEAL_BUDGET_MS = 4_000;
export const REVEAL_MIN_MS = 35;
/**
 * ★`[2026-10-03]` Measured on the real server (local, 26 rows): the server had sent everything 5.3 s after the press and the screen
 * finished drawing at 17.6 s — 12.2 s to replay, though the budget said 8 s. The floor above held each change to 35 ms, and every
 * drawn change also costs a render (~45 ms): 150-odd changes × ~80 ms. So a big backlog is drawn several changes at a time
 * (`revealBatch`) and the budget is 4 s.
 */
export const REVEAL_TICK_COST_MS = 45;

/** How many changes are drawn in one tick: 1 while the backlog fits the budget at one a tick, more when it does not. */
export function revealBatch(waiting: number): number {
  const ticks = Math.max(1, Math.floor(REVEAL_BUDGET_MS / (REVEAL_MIN_MS + REVEAL_TICK_COST_MS)));
  return Math.max(1, Math.ceil(waiting / ticks));
}

/**
 * ★`[2026-10-03 사용자 지적]` 맨 위 단계 표시(받았어요 → 일정 읽기 → 장소·운영시간 → 정리 완료)에도 속도 조절이 있어야 한다. Each step of that bar
 * stays at least this long before the next one lights (the bar used to move on in one tick: 「받았어요」 was never seen).
 */
export const STAGE_MIN_MS = 900;

/**
 * Up to `count` changes toward `target` (fewer when it is reached first); null when nothing is left to draw.
 * ★A batch never crosses from one stage of the top bar to the next: the change of stage is the first step of a tick of its own, which waits `STAGE_MIN_MS`.
 */
export function stepMany(shown: PlanCheckView, target: PlanCheckView, count: number): PlanCheckView | null {
  let view: PlanCheckView | null = null;
  for (let at = 0; at < count; at += 1) {
    const from = view ?? shown;
    const next = nextStep(from, target);
    if (!next) break;
    if (view && next.stage !== from.stage) break;
    view = next;
  }
  return view;
}

/**
 * ★`[2026-10-03 사용자 지적]` 「줄 읽기」 도 천천히 하나씩 보여야 한다. The lines used to be drawn at the pace set by the WHOLE backlog (the check rows
 * that follow too), so a plan the server sent in one go had its lines ticked off in about 100 ms each — the reading screen flashed by. Reading the
 * lines now has a pace of its own: about this long for all of them (at most `REVEAL_MS` for each), never faster than `READ_MIN_MS` a step.
 */
export const READ_BUDGET_MS = 5_000;
export const READ_MIN_MS = 70;

/** The pause between two steps of reading the lines, when `work` steps (a line appearing, a line read) are waiting. */
export function readPause(work: number): number {
  return Math.min(REVEAL_MS, Math.max(READ_MIN_MS, Math.round(READ_BUDGET_MS / Math.max(1, work))));
}

/** Steps of reading still to draw: a line appearing, a line being ticked off. 0 once every line is drawn as it is in `target`. */
export function linesBacklog(shown: PlanCheckView, target: PlanCheckView): number {
  return target.lines.reduce((sum, line, at) => {
    const seen = shown.lines[at];
    return sum + (seen ? (!seen.read && line.read ? 1 : 0) : line.read ? 2 : 1);
  }, 0);
}

/** About how many drawn changes lie between `shown` and `target`: a line read, a place or leg appearing, each of its checks, its verdict, a stage. */
export function backlog(shown: PlanCheckView, target: PlanCheckView): number {
  const pending = <T extends { id: string; checks: CheckRow[]; verdict: Verdict | null }>(have: T[], want: T[]) => want.reduce((sum, entity) => {
    const seen = have.find((other) => other.id === entity.id);
    if (!seen) return sum + 2 + entity.checks.length;
    return sum + entity.checks.filter((row, at) => JSON.stringify(row) !== JSON.stringify(seen.checks[at])).length + (seen.verdict === entity.verdict ? 0 : 1);
  }, 0);
  const lines = linesBacklog(shown, target);
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
  const linePeak = useRef(0);
  // When the stage of the top bar last changed on screen (the clock of `STAGE_MIN_MS`).
  const stageSince = useRef<{ stage: PlanCheckView["stage"]; at: number } | null>(null);
  useEffect(() => {
    if (reduced) return;
    if (stageSince.current?.stage !== shown.stage) stageSince.current = { stage: shown.stage, at: performance.now() };
    if (!nextStep(shown, target)) { peak.current = 0; linePeak.current = 0; return; }
    peak.current = Math.max(peak.current, backlog(shown, target));
    // While lines are still being read they keep their own slow pace, one step at a time; the checks after them are drawn at the budgeted pace.
    const work = linesBacklog(shown, target);
    linePeak.current = work > 0 ? Math.max(linePeak.current, work) : 0;
    const reading = work > 0;
    const batch = reading ? 1 : revealBatch(peak.current);
    let wait = reading ? readPause(linePeak.current) : revealPause(peak.current, pause);
    // The next change moves the top bar on to its next stage: the stage that is showing has been there long enough first.
    const upcoming = nextStep(shown, target);
    if (upcoming && upcoming.stage !== shown.stage && stageSince.current) wait = Math.max(wait, STAGE_MIN_MS - (performance.now() - stageSince.current.at));
    const timer = setTimeout(() => { const next = stepMany(shown, target, batch); if (next) setShown(next); }, wait);
    return () => clearTimeout(timer);
  }, [shown, target, reduced, pause]);
  // ★The server's own count is not replayed: it is shown as it arrives, whatever row the drawing has got to (the rows follow at their pace).
  const live = useMemo(() => (shown.serverProgress === target.serverProgress ? shown : { ...shown, serverProgress: target.serverProgress }), [shown, target.serverProgress]);
  return reduced ? { view: target, settled: true } : { view: live, settled: nextStep(shown, target) === null };
}
