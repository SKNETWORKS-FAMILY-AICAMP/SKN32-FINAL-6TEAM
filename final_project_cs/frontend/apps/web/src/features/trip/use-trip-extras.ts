"use client";

import { useQuery } from "@tanstack/react-query";
import { getNotices, getProposals } from "@/lib/live/extras";
import { useSettings } from "@/lib/settings";

export const proposalsKey = (tripId: string, language: string) => ["proposals", tripId, language] as const;
export const noticesKey = (tripId: string, language: string) => ["notices", tripId, language] as const;

/** The server may open a choice or send a notice at any time (the watcher runs on its own), so these are re-read now and then. */
const REFRESH_MS = 30_000;

export function useProposals(tripId: string) {
  const { language } = useSettings();
  return useQuery({ queryKey: proposalsKey(tripId, language), queryFn: () => getProposals(tripId, language), retry: false, refetchInterval: REFRESH_MS });
}

export function useNotices(tripId: string) {
  const { language } = useSettings();
  return useQuery({ queryKey: noticesKey(tripId, language), queryFn: () => getNotices(tripId, language), retry: false, refetchInterval: REFRESH_MS });
}
