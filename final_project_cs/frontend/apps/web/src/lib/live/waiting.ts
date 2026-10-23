"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

/**
 * `[2026-10-06 사용자 지적 — 서버가 1분 넘게 답이 없는데 아무 알림이 없다]` Every call to the server that has not answered yet is counted here, so ONE place (`ServerWaitBanner`) can say the server is slow
 * whatever screen the customer is on. A call registers when it starts (`beginWait`) and leaves when it ends - answered, refused, timed out or aborted.
 *
 * `steps` = after how long (ms) the first, the second and the third notice show for THIS call. A plain call answers in seconds, so it is told from 8 s on; a streamed task (planning, a chat answer) is
 * slow by nature and tells its progress, so it is told from 30 s on - counted from its last sign of life (`touch`: a new stage), not from its start.
 * The reading stream of an intake and the other change streams are NOT counted (they stay open on purpose); the reading screen watches its own silence.
 */
export type WaitSteps = readonly [first: number, second: number, third: number];
/**
 * A plain call (`api`). `[2026-10-13 사용자 지시 · Codex 1회차 합의]` 첫 알림 8 s → 10 s — 화면에 아무 표시 없이 기다릴 때 사용자의 주의가 흐트러지는 한계
 * (Nielsen Norman Group 「응답 시간의 세 한계」 ≈10 s). 기록: 이 세션 스크래치 consensus/20261013_0240_wait_banner.
 */
export const CALL_STEPS: WaitSteps = [10_000, 30_000, 60_000];
/**
 * `[2026-10-13 사용자 지시 · Codex 1회차 합의]` A plain call whose screen already shows its own loading line (「다른 후보를 찾는 중…」 · 「찾는 중…」 ·
 * 「이동 경로 찾는 중…」): the customer knows it is working, so the global notice waits until the wait is abnormal. Such calls take ~15 s normally (candidates,
 * observed 2026-10-12) — a 20 s first notice would still fire on normal waits, so it starts at 30 s like a streamed task.
 */
export const SHOWN_STEPS: WaitSteps = [30_000, 60_000, 120_000];
/** A streamed task (`streamApi`). */
export const TASK_STEPS: WaitSteps = [30_000, 60_000, 120_000];

export interface Wait {
  /** A sign of life (a new stage): the count starts over. */
  touch: () => void;
  end: () => void;
}

interface Entry { id: number; since: number; steps: WaitSteps }

const entries = new Map<number, Entry>();
const listeners = new Set<() => void>();
let nextId = 1;
let size = 0;

const emit = () => { size = entries.size; listeners.forEach((listener) => listener()); };

export function beginWait(steps: WaitSteps = CALL_STEPS, now: () => number = Date.now): Wait {
  const id = nextId++;
  entries.set(id, { id, since: now(), steps });
  emit();
  return {
    touch: () => { const entry = entries.get(id); if (entry) entry.since = now(); },
    end: () => { if (entries.delete(id)) emit(); },
  };
}

/** 0 = nothing to say yet, 1 · 2 · 3 = the notice of that step. */
export function waitLevel(elapsedMs: number, steps: WaitSteps): 0 | 1 | 2 | 3 {
  return elapsedMs >= steps[2] ? 3 : elapsedMs >= steps[1] ? 2 : elapsedMs >= steps[0] ? 1 : 0;
}

export interface WorstWait { id: number; level: 1 | 2 | 3; seconds: number }

/** The call that has waited longest in its own terms (highest notice level, then longest wait); null when no call has reached its first notice. */
export function worstWait(now: number, all: Iterable<Pick<Entry, "id" | "since" | "steps">> = entries.values()): WorstWait | null {
  let worst: WorstWait | null = null;
  for (const entry of all) {
    const elapsed = now - entry.since;
    const level = waitLevel(elapsed, entry.steps);
    if (level === 0) continue;
    const seconds = Math.floor(elapsed / 1000);
    if (!worst || level > worst.level || (level === worst.level && seconds > worst.seconds)) worst = { id: entry.id, level, seconds };
  }
  return worst;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

/** The slowest call now, re-read every second while any call is waiting. */
export function useServerWait(): WorstWait | null {
  const waiting = useSyncExternalStore(subscribe, () => size, () => 0);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (waiting === 0) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [waiting]);
  return waiting === 0 ? null : worstWait(now);
}
