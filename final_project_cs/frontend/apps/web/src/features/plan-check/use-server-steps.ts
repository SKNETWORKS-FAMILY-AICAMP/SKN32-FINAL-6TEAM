"use client";

import { useEffect, useState } from "react";
import type { PlanCheckView } from "./model";
import { planSteps, type Steps } from "./server-steps";

/**
 * `[2026-10-24 사용자 확정 — 진행 표시 ③ · ST4F-732]` The server's steps for the bar (`planSteps`) and how long the step it is at has had no news, in seconds
 * (counted every second while a step is running; it starts again at 0 each time a count comes in — `quietText` shows it past 8 s).
 * The 「답 반영」 cell, once there (questions read while it read), stays: answering them takes the question away before the server puts the answers in.
 */
export function useServerSteps(view: Pick<PlanCheckView, "stage" | "serverPhases" | "asks" | "lines" | "ended">): { steps: Steps; quiet: number } {
  const asked = Boolean(view.asks?.length);
  const [withAnswers, setWithAnswers] = useState(asked);
  if (asked && !withAnswers) setWithAnswers(true);
  const steps = planSteps(view, withAnswers);
  const news = JSON.stringify(view.serverPhases ?? {});
  const running = steps.current !== null;
  const [tick, setTick] = useState({ news, seconds: 0 });
  useEffect(() => {
    if (!running) return;
    const since = performance.now();
    const timer = setInterval(() => setTick({ news, seconds: (performance.now() - since) / 1000 }), 1000);
    return () => clearInterval(timer);
  }, [news, running]);
  return { steps, quiet: running && tick.news === news ? tick.seconds : 0 };
}
