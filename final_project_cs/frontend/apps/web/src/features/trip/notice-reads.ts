"use client";

import { useSyncExternalStore } from "react";

/**
 * `[2026-10-07 사용자 결정 — 목업 C안 ① 알림 센터]` Which of a trip's notices this browser has seen: a notice counts as read once the 「받은 알림」 tab has shown it.
 * ★Kept in THIS browser only (local storage): the server keeps no read state yet (asked of the backend — `wiki/external/web-screen-api.md`), so another device or a cleared
 * browser counts the same notices as new again.
 */
const KEY = "tripilot.web.noticeReads.v1";
const NONE: readonly string[] = [];

type Reads = Record<string, readonly string[]>;
let cache: Reads | null = null;
const listeners = new Set<() => void>();

function load(): Reads {
  try {
    const raw = JSON.parse(window.localStorage.getItem(KEY) ?? "null") as unknown;
    if (!raw || typeof raw !== "object") return {};
    return Object.fromEntries(Object.entries(raw as Record<string, unknown>).filter((entry): entry is [string, string[]] => Array.isArray(entry[1]) && entry[1].every((key) => typeof key === "string")));
  } catch { return {}; }
}

function reads(): Reads {
  cache ??= load();
  return cache;
}

/** The notices of this trip shown in the 「받은 알림」 tab: from here on they are not counted as new. */
export function markNoticesSeen(tripId: string, keys: readonly string[]) {
  const before = reads()[tripId] ?? NONE;
  const added = keys.filter((key) => !before.includes(key));
  if (added.length === 0) return;
  cache = { ...reads(), [tripId]: [...before, ...added] };
  try { window.localStorage.setItem(KEY, JSON.stringify(cache)); } catch { /* private window: kept for this page only */ }
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

/** The keys of this trip's notices this browser has seen (none on the server render). */
export function useSeenNotices(tripId: string): readonly string[] {
  return useSyncExternalStore(subscribe, () => reads()[tripId] ?? NONE, () => NONE);
}
