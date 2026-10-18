"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getNotices, getProposals } from "@/lib/live/extras";
import { getRecovery } from "@/lib/live/recovery";
import { useSettings } from "@/lib/settings";
import { useNeedsPolling } from "./watch-mode";
import { getTripRisks } from "@/lib/live/risks";
import { requestRiskRefresh, riskQueryOptions } from "./risk-query";

export const proposalsKey = (tripId: string, language: string) => ["proposals", tripId, language] as const;
export const noticesKey = (tripId: string, language: string) => ["notices", tripId, language] as const;
export const recoveryKey = (tripId: string, language: string) => ["recovery", tripId, language] as const;
export const risksKey = (tripId: string, language: string, version?: number) =>
  ["trip-risks", tripId, language, ...(typeof version === "number" ? [version] : [])] as const;

/** First entry fills missing cache within the existing budget; periodic reads never force provider calls. */
export function useTripRisks(tripId: string, version?: number) {
  const { language } = useSettings();
  const queryClient = useQueryClient();
  const key = risksKey(tripId, language, version);
  const query = useQuery(riskQueryOptions(queryClient, key, (fresh) => getTripRisks(tripId, language, fresh)));
  const refresh = () => { requestRiskRefresh(queryClient, key); void query.refetch({ cancelRefetch: false }); };
  return { ...query, refresh };
}

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
  // `[2026-10-17 ST4F-603]` 정지가 풀리면 생긴다 — 초인종의 알림 신호(`use-trip-events.ts`)와 탭 복귀 때 다시 읽는다.
  return useQuery({ queryKey: recoveryKey(tripId, language), queryFn: () => getRecovery(tripId, language), retry: false, staleTime: 30_000, refetchOnWindowFocus: true });
}
