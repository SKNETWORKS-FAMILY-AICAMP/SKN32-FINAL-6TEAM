"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getNotices, getProposals, type Notice } from "@/lib/live/extras";
import { useSettings } from "@/lib/settings";
import { tripKey } from "./use-trip";

export const proposalsKey = (tripId: string, language: string) => ["proposals", tripId, language] as const;
export const noticesKey = (tripId: string, language: string) => ["notices", tripId, language] as const;

/** 서버가 만든 제안과 알림을 1분 간격으로 확인한다. */
const REFRESH_MS = 60_000;

export function useProposals(tripId: string) {
  const { language } = useSettings();
  return useQuery({ queryKey: proposalsKey(tripId, language), queryFn: () => getProposals(tripId, language), retry: false, refetchInterval: REFRESH_MS });
}

export function useNotices(tripId: string) {
  const { language } = useSettings();
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: noticesKey(tripId, language),
    queryFn: async () => {
      const previous = queryClient.getQueryData<Notice[]>(noticesKey(tripId, language));
      const notices = await getNotices(tripId, language);
      if (JSON.stringify(previous ?? []) !== JSON.stringify(notices)) {
        // 첫 알림 조회도 동기화해 여행을 연 직후 생긴 변경을 놓치지 않는다.
        // 여행 조회가 실패하면 알림 캐시를 갱신하지 않아 다음 주기에 다시 시도한다.
        await queryClient.invalidateQueries({ queryKey: tripKey(tripId, language) }, { throwOnError: true });
      }
      return notices;
    },
    retry: false,
    refetchInterval: REFRESH_MS,
  });
}
