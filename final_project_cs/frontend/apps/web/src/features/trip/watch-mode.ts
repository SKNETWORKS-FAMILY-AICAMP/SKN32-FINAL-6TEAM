"use client";

import { useSyncExternalStore } from "react";

/**
 * How an open trip screen learns about server-side changes: the server's bell (`use-trip-events.ts`), or — only
 * when the server has no bell — re-reading notices and proposals every 30 s. Kept apart so the query hooks and the
 * bell listener do not import each other.
 */
type Mode = "bell" | "polling";
const modes = new Map<string, Mode>();
const listeners = new Set<() => void>();

export function setWatchMode(tripId: string, mode: Mode) {
  if (modes.get(tripId) === mode) return;
  modes.set(tripId, mode);
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

/** Whether this trip's notices and proposals must re-read themselves on a timer (only when the server has no bell). */
export function useNeedsPolling(tripId: string): boolean {
  return useSyncExternalStore(subscribe, () => modes.get(tripId) === "polling", () => false);
}
