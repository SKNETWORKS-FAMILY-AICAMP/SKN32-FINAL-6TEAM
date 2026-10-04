"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useSettings } from "@/lib/settings";
import { isInstantRow, nextStep, STAGES, type CheckRow, type PlanCheckView, type Verdict } from "./model";

/**
 * ★`[2026-10-04 사용자 지시 · 코덱스 의견]` 확인 표시는 사용자가 「이건 확인됐구나」를 알아볼 속도로 켜진다 — 한 줄이 켜지고 다음 줄이 켜지기까지 300ms
 * (켜지는 표시 자체는 그 안의 200ms, `plan-check.module.css` 의 `markPop`). 앞 판은 4초 안에 전부 그리려고 줄당 35ms까지 줄이고 한꺼번에 여러 개를 그려서
 * 「후루룩 지나가 뭘 확인했는지 알 수 없다」는 지적을 받았다. 빨강·회색 줄은 애니메이션 없이 확정되고(`isInstantRow`), 이동 줄은 한 번에 나온다.
 */
export const REVEAL_MS = 300;
/**
 * 서버 답이 온 뒤의 재생 상한. 줄 하나씩 그리면 이 안에 끝나지 않을 만큼 큰 계획(줄 간격이 `REVEAL_MIN_MS` 아래로 내려가야 하는 경우)은 줄 단위가 아니라
 * **카드 단위**로 그린다 — 한 카드가 완성된 채 나오고 다음 카드가 그 뒤에 나온다. 줄 간격을 더 줄이지 않는다(줄이면 다시 후루룩 지나간다).
 */
export const REVEAL_BUDGET_MS = 14_000;
export const REVEAL_MIN_MS = 200;
/** 카드 단위로 그릴 때 카드 사이의 가장 짧은 간격. */
export const COARSE_MIN_MS = 120;

/**
 * ★`[2026-10-03 사용자 지적]` 맨 위 단계 표시(받았어요 → 일정 읽기 → 장소·운영시간 → 정리 완료)에도 속도 조절이 있어야 한다. Each step of that bar
 * stays at least this long before the next one lights (the bar used to move on in one tick: 「받았어요」 was never seen).
 */
export const STAGE_MIN_MS = 900;

/** Up to `count` changes toward `target` (fewer when it is reached first); null when nothing is left to draw. `coarse` = card by card, not line by line. */
export function stepMany(shown: PlanCheckView, target: PlanCheckView, count: number, coarse = false): PlanCheckView | null {
  let view: PlanCheckView | null = null;
  for (let at = 0; at < count; at += 1) {
    const from = view ?? shown;
    const next = nextStep(from, target, coarse);
    if (!next) break;
    // ★A batch never crosses from one stage of the top bar to the next: the change of stage is the first step of a tick of its own, which waits `STAGE_MIN_MS`.
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

type Checked = { id: string; checks: CheckRow[]; verdict: Verdict | null };

/** The drawn changes line by line still ahead of `shown` for places (a card appearing, each check that is ticked in, the verdict when no check carries it) and legs (one each). */
function lineSteps<T extends Checked>(have: T[], want: T[], leg: boolean): number {
  return want.reduce((sum, entity) => {
    const seen = have.find((other) => other.id === entity.id);
    if (leg) return sum + (seen && JSON.stringify(seen) === JSON.stringify(entity) ? 0 : 1);
    const ticks = (rows: CheckRow[], from?: CheckRow[]) => rows.filter((row, at) => !isInstantRow(row) && (!from || JSON.stringify(row) !== JSON.stringify(from[at]))).length;
    if (!seen) return sum + 1 + Math.max(1, ticks(entity.checks));
    const left = seen.checks.length === entity.checks.length ? ticks(entity.checks, seen.checks) : 1;
    return sum + left + (left === 0 && seen.verdict !== entity.verdict ? 1 : 0);
  }, 0);
}

/** About how many drawn changes lie between `shown` and `target` when each check is drawn on its own: lines read, cards, checks, verdicts, legs, stages. */
export function backlog(shown: PlanCheckView, target: PlanCheckView): number {
  return linesBacklog(shown, target) + lineSteps(shown.items, target.items, false) + lineSteps(shown.moves, target.moves, true)
    + Math.max(0, STAGES.indexOf(target.stage) - STAGES.indexOf(shown.stage));
}

/** The same count when a card is drawn whole: one for each card or leg not yet as it should be. */
export function cardBacklog(shown: PlanCheckView, target: PlanCheckView): number {
  const behind = (have: Checked[], want: Checked[]) => want.filter((entity) => JSON.stringify(have.find((other) => other.id === entity.id)) !== JSON.stringify(entity)).length;
  return behind(shown.items, target.items) + behind(shown.moves, target.moves);
}

/**
 * How the waiting changes are drawn: the pause before the next one, and whether line by line or card by card. `lines` is the most that has been waiting
 * line by line, `cards` card by card (the most since the screen last caught up: the pace is set by that, not by what is left).
 */
export function revealPlan(lines: number, cards: number): { pause: number; coarse: boolean } {
  const fine = Math.min(REVEAL_MS, Math.round(REVEAL_BUDGET_MS / Math.max(1, lines)));
  if (fine >= REVEAL_MIN_MS) return { pause: fine, coarse: false };
  return { pause: Math.min(REVEAL_MS, Math.max(COARSE_MIN_MS, Math.round(REVEAL_BUDGET_MS / Math.max(1, cards)))), coarse: true };
}

/**
 * The snapshot to draw, and whether it has caught up with `target`. The first snapshot is drawn as it is (a reload or a
 * late open shows where things stand, without replaying); every later one is reached one change at a time (`nextStep`).
 * With the menu's 「애니메이션 건너뛰기」 on it is drawn at once.
 */
export function useReveal(target: PlanCheckView): { view: PlanCheckView; settled: boolean } {
  // ★`[2026-10-03 사용자 결정]` Skipping is the customer's own choice in the menu (「애니메이션 건너뛰기」), not the system's 「동작 줄이기」: the steps are
  //   information (how far the check is), and movement the system asked to reduce is already off (`globals.css` ends every transition and animation).
  const { skipAnimation: reduced } = useSettings();
  const [shown, setShown] = useState(target);
  // The most that has been waiting since the screen last caught up: the pace is set by that, not by what is left.
  const peak = useRef({ lines: 0, cards: 0, reading: 0 });
  // When the stage of the top bar last changed on screen (the clock of `STAGE_MIN_MS`).
  const stageSince = useRef<{ stage: PlanCheckView["stage"]; at: number } | null>(null);
  useEffect(() => {
    if (reduced) return;
    if (stageSince.current?.stage !== shown.stage) stageSince.current = { stage: shown.stage, at: performance.now() };
    if (!nextStep(shown, target)) { peak.current = { lines: 0, cards: 0, reading: 0 }; return; }
    peak.current = { lines: Math.max(peak.current.lines, backlog(shown, target)), cards: Math.max(peak.current.cards, cardBacklog(shown, target)), reading: peak.current.reading };
    // While lines are still being read they keep their own slow pace, one step at a time; the checks after them are drawn at the pace of `revealPlan`.
    const work = linesBacklog(shown, target);
    peak.current.reading = work > 0 ? Math.max(peak.current.reading, work) : 0;
    const reading = work > 0;
    const plan = revealPlan(peak.current.lines, peak.current.cards);
    let wait = reading ? readPause(peak.current.reading) : plan.pause;
    // The next change moves the top bar on to its next stage: the stage that is showing has been there long enough first.
    const upcoming = nextStep(shown, target);
    if (upcoming && upcoming.stage !== shown.stage && stageSince.current) wait = Math.max(wait, STAGE_MIN_MS - (performance.now() - stageSince.current.at));
    const timer = setTimeout(() => { const next = stepMany(shown, target, 1, !reading && plan.coarse); if (next) setShown(next); }, wait);
    return () => clearTimeout(timer);
  }, [shown, target, reduced]);
  // ★The server's own count is not replayed: it is shown as it arrives, whatever row the drawing has got to (the rows follow at their pace).
  const live = useMemo(() => (shown.serverProgress === target.serverProgress ? shown : { ...shown, serverProgress: target.serverProgress }), [shown, target.serverProgress]);
  return reduced ? { view: target, settled: true } : { view: live, settled: nextStep(shown, target) === null };
}
