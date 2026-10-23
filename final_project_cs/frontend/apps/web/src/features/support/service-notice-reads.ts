"use client";

import { useSyncExternalStore } from "react";

const KEEP = 100;
const NONE: readonly string[] = [];

/** One list of service notice ids kept in this browser (local storage), newest last, at most 100. ★This browser only — the server keeps no such state. */
function idStore(key: string) {
  let cache: readonly string[] | null = null;
  const listeners = new Set<() => void>();
  const read = (): readonly string[] => {
    if (cache) return cache;
    try {
      const raw = JSON.parse(window.localStorage.getItem(key) ?? "null") as unknown;
      cache = Array.isArray(raw) ? raw.filter((id): id is string => typeof id === "string") : NONE;
    } catch { cache = NONE; }
    return cache;
  };
  const add = (ids: readonly string[]) => {
    const before = read();
    const added = ids.filter((id) => !before.includes(id));
    if (added.length === 0) return;
    cache = [...before, ...added].slice(-KEEP);
    try { window.localStorage.setItem(key, JSON.stringify(cache)); } catch { /* private window: kept for this page only */ }
    listeners.forEach((listener) => listener());
  };
  const subscribe = (listener: () => void) => {
    listeners.add(listener);
    return () => { listeners.delete(listener); };
  };
  return { read, add, subscribe };
}

/**
 * `[2026-10-17 사용자 결정 — ST4F-604]` Which service notices (the operator's notices, not a trip's) this browser has seen. The trip screen's bell counts the
 * ones not seen yet; the notice center's 「공지」 tab marks the ones it shows as seen.
 */
const reads = idStore("tripilot.web.serviceNoticeReads.v1");
export const markServiceNoticesSeen = reads.add;
export function useSeenServiceNotices(): readonly string[] {
  return useSyncExternalStore(reads.subscribe, reads.read, () => NONE);
}

/**
 * `[2026-10-17 사용자 결정 — ST4F-608]` Which service notices this browser closed with the banner's 「공지 닫기」 (maintenance as `maintenance:<its end>`) — the banner
 * leaves them out until a new one comes, also after a reload (before: the page's memory only, so a reload put the same notice back).
 */
const dismissals = idStore("tripilot.web.serviceNoticeDismissed.v1");
export const dismissServiceNotices = dismissals.add;
export function useDismissedServiceNotices(): readonly string[] {
  return useSyncExternalStore(dismissals.subscribe, dismissals.read, () => NONE);
}
