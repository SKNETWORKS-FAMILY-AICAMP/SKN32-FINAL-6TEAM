"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { nextStep, type PlanCheckView } from "./model";

/** Pause between two drawn changes — slow enough to follow, short enough that a whole plan takes about ten seconds. */
export const REVEAL_MS = 280;

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
  useEffect(() => {
    if (reduced) return;
    const next = nextStep(shown, target);
    if (!next) return;
    const timer = setTimeout(() => setShown(next), pause);
    return () => clearTimeout(timer);
  }, [shown, target, reduced, pause]);
  return reduced ? { view: target, settled: true } : { view: shown, settled: nextStep(shown, target) === null };
}
