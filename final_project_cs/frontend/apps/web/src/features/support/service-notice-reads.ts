"use client";

import { useSyncExternalStore } from "react";

/**
 * `[2026-10-17 사용자 결정 — ST4F-604]` Which service notices (the operator's notices, not a trip's) this browser has seen. The trip screen's bell counts the
 * ones not seen yet; opening the notice center marks the ones it shows as seen. ★This browser only (local storage) — the server keeps no read state.
 */
const KEY = "tripilot.web.serviceNoticeReads.v1";
const KEEP = 100;
const NONE: readonly string[] = [];
let cache: readonly string[] | null = null;
const listeners = new Set<() => void>();

function seen(): readonly string[] {
  if (cache) return cache;
  try {
    const raw = JSON.parse(window.localStorage.getItem(KEY) ?? "null") as unknown;
    cache = Array.isArray(raw) ? raw.filter((id): id is string => typeof id === "string") : NONE;
  } catch { cache = NONE; }
  return cache;
}

export function markServiceNoticesSeen(ids: readonly string[]) {
  const before = seen();
  const added = ids.filter((id) => !before.includes(id));
  if (added.length === 0) return;
  cache = [...before, ...added].slice(-KEEP);
  try { window.localStorage.setItem(KEY, JSON.stringify(cache)); } catch { /* private window: kept for this page only */ }
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

export function useSeenServiceNotices(): readonly string[] {
  return useSyncExternalStore(subscribe, seen, () => NONE);
}
