"use client";

import { useEffect, useState } from "react";

/**
 * `[2026-10-06 사용자 지적 — 서버가 1분 넘게 답이 없는데 아무 알림이 없다]` How many whole seconds `signal` has stayed the same (0 while `active` is false). The reading screen lives on the server's own progress stream,
 * which stays open and so is not counted by `waiting.ts`: it says what changed in the plan by `signal` (a new line read, a new stage), and this hook says for how long nothing did.
 * The count starts over when `signal` or `active` changes, from the next tick on (the clock is read in the timer, never while drawing).
 */
export function useQuiet(signal: string, active: boolean): number {
  const key = `${active ? 1 : 0}|${signal}`;
  const [now, setNow] = useState(0);
  const [seen, setSeen] = useState<{ key: string; at: number | null }>({ key, at: null });
  if (seen.key !== key) setSeen({ key, at: null });
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => {
      const time = Date.now();
      setNow(time);
      setSeen((current) => current.at === null ? { ...current, at: time } : current);
    }, 1000);
    return () => clearInterval(id);
  }, [active, key]);
  return active && seen.at !== null ? Math.max(0, Math.floor((now - seen.at) / 1000)) : 0;
}
