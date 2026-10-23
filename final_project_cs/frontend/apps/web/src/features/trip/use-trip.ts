"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSettings } from "@/lib/settings";
import { tripGateway, tripKey, tripsKey } from "../../lib/gateway";
import { deleteTrips } from "./delete-trips";

export { tripKey, tripsKey } from "../../lib/gateway";

export function useTrip(tripId: string) {
  const { language } = useSettings();
  return useQuery({
    queryKey: tripKey(tripId, language),
    queryFn: () => tripGateway.getTrip(tripId, language),
    enabled: Boolean(tripId),
    retry: false,
    refetchOnWindowFocus: false,
    // `[2026-10-07]` A language change reads the trip again: meanwhile the same trip in the language before stays on screen, so the trip screen (its frame and the open menu) does not
    // give way to the loading page. Never another trip's plan.
    placeholderData: (previous, previousQuery) => previousQuery?.queryKey[1] === tripId ? previous : undefined,
  });
}

/** This browser's trips, newest first. The home card and "My trips" share this one query. */
export function useTrips({ enabled = true }: { enabled?: boolean } = {}) {
  const { language } = useSettings();
  return useQuery({
    enabled,
    queryKey: [...tripsKey, language],
    queryFn: () => tripGateway.listTrips(language),
    retry: false,
    // `[2026-10-17 ST4F-603]` 에이전트 · MCP · 다른 기기에서 등록한 여행도 있다 — 탭으로 돌아오면 다시 읽는다.
    refetchOnWindowFocus: true,
  });
}

/** `deleteTrips` for this screen: each trip is deleted on the server, and the cached trips and list are dropped for the ones that went. */
export function useDeleteTrips() {
  const queryClient = useQueryClient();
  const { language } = useSettings();
  return (ids: readonly string[]) => deleteTrips(ids, (id) => tripGateway.deleteTrip(id, language), queryClient);
}
