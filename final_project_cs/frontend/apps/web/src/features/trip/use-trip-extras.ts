"use client";

import { useQuery } from "@tanstack/react-query";
import { getNotices, getProposals } from "@/lib/live/extras";
import { getRecovery } from "@/lib/live/recovery";
import { useSettings } from "@/lib/settings";
import { useNeedsPolling } from "./watch-mode";

export const proposalsKey = (tripId: string, language: string) => ["proposals", tripId, language] as const;
export const noticesKey = (tripId: string, language: string) => ["notices", tripId, language] as const;
export const recoveryKey = (tripId: string, language: string) => ["recovery", tripId, language] as const;

/**
 * The server may open a choice or send a notice at any time (the watcher runs on its own). Its bell
 * (`use-trip-events.ts`) says when; only a server without the bell leaves these to be re-read every 30 s.
 */
const REFRESH_MS = 30_000;

export function useProposals(tripId: string) {
  const { language } = useSettings();
  const polling = useNeedsPolling(tripId);
  return useQuery({ queryKey: proposalsKey(tripId, language), queryFn: () => getProposals(tripId, language), retry: false, refetchInterval: polling ? REFRESH_MS : false });
}

export function useNotices(tripId: string) {
  const { language } = useSettings();
  const polling = useNeedsPolling(tripId);
  return useQuery({ queryKey: noticesKey(tripId, language), queryFn: () => getNotices(tripId, language), retry: false, refetchInterval: polling ? REFRESH_MS : false });
}

/** `[2026-10-06]` The situation brief after a disaster pause was lifted (null when there is none or it is older than 72 hours). A server without it reads as none; a read that fails otherwise is the caller's to show. */
export function useRecovery(tripId: string) {
  const { language } = useSettings();
  return useQuery({ queryKey: recoveryKey(tripId, language), queryFn: () => getRecovery(tripId, language), retry: false, staleTime: 30_000 });
}
