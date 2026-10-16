"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

/**
 * `[2026-10-16 사용자 결정 — ST4F-601 뒤로가기 묶음]` The screen this page was on just before, inside the app (`null` when the app was loaded straight onto this screen).
 * A sub-screen of Settings goes back with the browser's back only when it was opened from Settings; otherwise it would leave the app or ping-pong
 * between Settings and the sub-screen (Settings ← is the browser's back, the sub-screen ← used to push Settings — 2026-10-16 flow check F7).
 * It lives in page memory: a full load (a sign-in or Discord coming back) starts it over.
 */
let current: string | null = null;
let previous: string | null = null;
let replacing = false;

export function previousPath(): string | null {
  return previous;
}

/** Call right before `router.replace`: the screen being replaced adds no history entry, so it is not a screen to go back to. */
export function nextIsReplace(): void {
  replacing = true;
}

export function usePathTracker(): void {
  const pathname = usePathname();
  useEffect(() => {
    if (current !== null && current !== pathname) {
      previous = replacing ? null : current;
      replacing = false;
    }
    current = pathname;
  }, [pathname]);
}
