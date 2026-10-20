"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useSettings } from "@/lib/settings";
import { beginRecheck, cutAtStop, nextStep, onlyCard, rebase, stopAt, type PlanCheckView } from "./model";

/**
 * ★`[2026-10-04 사용자 지시 · 코덱스 의견]` 확인 표시는 사용자가 「이건 확인됐구나」를 알아볼 속도로 켜진다 — 한 줄이 켜지고 다음 줄이 켜지기까지 300ms
 * (켜지는 표시 자체는 그 안의 200ms, `plan-check.module.css` 의 `markPop`). 앞 판은 4초 안에 전부 그리려고 줄당 35ms까지 줄이고 한꺼번에 여러 개를 그려서
 * 「후루룩 지나가 뭘 확인했는지 알 수 없다」는 지적을 받았다.
 * `[2026-10-20]` 이 간격은 이제 줄 읽기(`readPause`)와 「다시 제출」 뒤 다시 켜는 표시에 쓴다. 처음 검사의 속도는 아래 C안 값이다.
 */
export const REVEAL_MS = 300;

/**
 * ★`[2026-10-20 사용자 결정 — 계획 확인 C안]` 처음 검사를 그리는 속도(흐름 목업 `mockups/tripilot-plan-flow-register.html` 4단계 · 비교 화면의 「끊김 고친 첫 판」):
 * 검사가 시작되고 0.7초 뒤 첫 카드가 모든 줄 「확인 중」으로 나오고 → 0.65초 → 줄마다 0.26초 → 마지막 줄 0.28초 뒤 판정 → 0.45초 뒤 다음 카드(그리로 가는 이동 줄과 함께)가 나오며
 * 앞 카드는 접힌다. 계획이 길어도 같은 속도다(앞 판의 14초 상한 · 카드 단위 그리기는 없앴다 — 기다리기 싫으면 메뉴의 「애니메이션 건너뛰기」).
 */
export const FIRST_CARD_MS = 700;
export const ROWS_LEAD_MS = 650;
export const ROW_MS = 260;
export const VERDICT_MS = 280;
export const FOLD_MS = 450;

/**
 * ★`[2026-10-03 사용자 지적]` 맨 위 단계 표시(받았어요 → 일정 읽기 → 장소·운영시간 → 정리 완료)에도 속도 조절이 있어야 한다. Each step of that bar
 * stays at least this long before the next one lights (the bar used to move on in one tick: 「받았어요」 was never seen).
 */
export const STAGE_MIN_MS = 900;

/** Up to `count` changes toward `target` (fewer when it is reached first); null when nothing is left to draw. */
export function stepMany(shown: PlanCheckView, target: PlanCheckView, count: number): PlanCheckView | null {
  let view: PlanCheckView | null = null;
  for (let at = 0; at < count; at += 1) {
    const from = view ?? shown;
    const next = nextStep(from, target);
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

/**
 * How long the screen rests before it draws `next` after `shown` (outside the reading of the lines — `readPause`): the C안 pace above. A new card waits the
 * fold of the one before (the first card a little longer: the map has just come), its first check the lead, each check after it `ROW_MS`, the verdict `VERDICT_MS`.
 * Anything else (a leg the server sent late, the days, the title) one check's pause.
 */
export function pauseBefore(shown: PlanCheckView, next: PlanCheckView): number {
  if (next.items.some((item) => !shown.items.some((other) => other.id === item.id))) return shown.items.length ? FOLD_MS : FIRST_CARD_MS;
  for (const item of next.items) {
    const was = shown.items.find((other) => other.id === item.id);
    if (!was || JSON.stringify(was) === JSON.stringify(item)) continue;
    if (JSON.stringify(was.checks) === JSON.stringify(item.checks)) return VERDICT_MS;
    return was.checks.every((row) => row.result === "pending") ? ROWS_LEAD_MS : ROW_MS;
  }
  return ROW_MS;
}

/**
 * The snapshot to draw, and whether it has caught up with `target`. The first snapshot is drawn as it is (a reload or a
 * late open shows where things stand, without replaying); changes during the first check are reached one at a time (`nextStep`).
 * After the check is done, edits are shown together: another action must use the whole saved plan, not a partially replayed edit.
 * With the menu's 「애니메이션 건너뛰기」 on it is drawn at once.
 *
 * ★`[2026-10-20 사용자 결정 — 계획 확인 C안]` With `stops` on (the page can change places), the first check stops at the first card that needs a look once the server's check is final
 * (`stopAt`): `stop` says which, and nothing past it is drawn. `recheck.begin` is called when the customer picks: the card's checks wait again where they stand and, once the
 * server answers with a new revision, they are ticked in again (`rebase`) — the replay goes on when the card passes, or stops at it again. `settling` is true from the pick until
 * the card's verdict is in. Not settled while stopped. With 「애니메이션 건너뛰기」 on, the check this page watches is drawn at once up to that card (`cutAtStop`) and stops there too.
 * `[2026-10-20 사용자 결정 — 다시 들어오면 결과 화면]` A page that opens on a check already finished (left before registering, then opened again) shows the result as before — the
 * result screen is where it is changed then (it keeps its tools: 2026-10-20 the read-only result was dropped) — so it does not stop.
 */
export interface RevealStop { id: string; settling: boolean }
export function useReveal(target: PlanCheckView, paused = false, stops = false): {
  view: PlanCheckView; settled: boolean; stop: RevealStop | null;
  recheck: { begin: (id: string) => void; fail: (id: string) => void };
  /** `[2026-10-20 C안]` This page drew the check (it was not finished when the page opened) — the 5-second 「여행 등록」 bar is for such a check only. */
  watched: boolean;
} {
  // ★`[2026-10-03 사용자 결정]` Skipping is the customer's own choice in the menu (「애니메이션 건너뛰기」), not the system's 「동작 줄이기」: the steps are
  //   information (how far the check is), and movement the system asked to reduce is already off (`globals.css` ends every transition and animation).
  const { skipAnimation: reduced } = useSettings();
  const [shown, setShown] = useState(target);
  const [wasPaused, setWasPaused] = useState(paused);
  // `[2026-10-20]` The check was already finished when the page opened: the result, as before (it stops only for a check this page watches).
  const [openedDone] = useState(target.stage === "done");
  const stopping = stops && !openedDone;
  // `[2026-10-20 C안]` A pick sent for the stopped card, and the revision it was sent on: nothing is drawn until the server answers with another one.
  const [asked, setAsked] = useState<{ id: string; revision: number | undefined } | null>(null);
  // Questions showed the completed reading progress, but not the map's cards. Begin their first appearance at checking.
  const completedHold = wasPaused && !paused && target.stage === "done";
  const firstMap = completedHold && shown.stage !== "done" && !reduced;
  if (wasPaused !== paused) setWasPaused(paused);
  if (firstMap) setShown({ ...target, stage: "checking", items: [], moves: [] });
  // `[2026-10-20 C안]` Skipping the animation still stops to ask: the check is drawn at once up to the first card that needs a look.
  const cut = useMemo(() => stopping && reduced ? cutAtStop(target) : target, [stopping, reduced, target]);
  const immediate = !paused && !firstMap && (reduced ? cut === target : shown.stage === "done" && target.stage === "done");
  // Keep the state in step with what is returned before another render can pause or restart the replay.
  // This guarded update adjusts only this hook's component; an effect would leave the old snapshot until after commit.
  if (immediate && shown !== target) setShown(target);
  if (asked && target.revision !== asked.revision) { setAsked(null); setShown(rebase(shown, target, asked.id)); }
  else if (!paused && !immediate && cut !== target && !asked && JSON.stringify(shown) !== JSON.stringify(cut)) setShown(cut);
  const stopId = stopping && !immediate ? stopAt(shown, target) : null;
  // The most reading steps that have been waiting since the screen last caught up: the reading pace is set by that, not by what is left.
  const peak = useRef(0);
  // When the stage of the top bar last changed on screen (the clock of `STAGE_MIN_MS`).
  const stageSince = useRef<{ stage: PlanCheckView["stage"]; at: number } | null>(null);
  useEffect(() => {
    if (paused || asked) return;
    if (immediate) {
      peak.current = 0;
      if (stageSince.current?.stage !== target.stage) stageSince.current = { stage: target.stage, at: performance.now() };
      return;
    }
    if (stageSince.current?.stage !== shown.stage) stageSince.current = { stage: shown.stage, at: performance.now() };
    const upcoming = stepMany(shown, target, 1);
    if (!upcoming) { peak.current = 0; return; }
    // Stopped at a card: only that card is drawn (its checks ticked in again after a pick); nothing past it.
    if (stopId && !onlyCard(shown, upcoming, stopId)) return;
    // While lines are still being read they keep their own slow pace, one step at a time; the checks after them are drawn at the C안 pace (`pauseBefore`).
    const work = linesBacklog(shown, target);
    peak.current = work > 0 ? Math.max(peak.current, work) : 0;
    let wait = work > 0 ? readPause(peak.current) : pauseBefore(shown, upcoming);
    // The next change moves the top bar on to its next stage: the stage that is showing has been there long enough first.
    if (upcoming.stage !== shown.stage && stageSince.current) wait = Math.max(wait, STAGE_MIN_MS - (performance.now() - stageSince.current.at));
    const timer = setTimeout(() => setShown(upcoming), wait);
    return () => clearTimeout(timer);
  }, [shown, target, immediate, paused, asked, stopId]);
  // ★The server's own count is not replayed: it is shown as it arrives, whatever row the drawing has got to (the rows follow at their pace).
  const live = useMemo(() => (shown.serverProgress === target.serverProgress ? shown : { ...shown, serverProgress: target.serverProgress }), [shown, target.serverProgress]);
  const recheck = {
    begin: (id: string) => { setAsked({ id, revision: target.revision }); setShown((current) => beginRecheck(current, id)); },
    // The pick was refused: the card is as the server still has it.
    fail: (id: string) => {
      setAsked(null);
      const kept = target.items.find((item) => item.id === id);
      setShown((current) => ({ ...current, items: current.items.map((item) => item.id === id && kept ? kept : item) }));
    },
  };
  if (immediate) return { view: target, settled: true, stop: null, recheck, watched: !openedDone };
  const settling = Boolean(asked) || (stopId !== null && JSON.stringify(shown.items.find((item) => item.id === stopId)) !== JSON.stringify(target.items.find((item) => item.id === stopId)));
  return { view: live, settled: !paused && !asked && !stopId && nextStep(shown, target) === null, stop: stopId ? { id: stopId, settling } : null, recheck, watched: !openedDone };
}
