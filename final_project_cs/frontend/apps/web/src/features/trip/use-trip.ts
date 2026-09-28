"use client";

import { useQuery } from "@tanstack/react-query";
import { useSettings } from "@/lib/settings";
import { tripGateway, tripKey, tripsKey } from "../../lib/gateway";

export { tripKey, tripsKey } from "../../lib/gateway";

export function useTrip(tripId: string) {
  const { language } = useSettings();
  return useQuery({
    queryKey: tripKey(tripId, language),
    queryFn: () => tripGateway.getTrip(tripId, language),
    enabled: Boolean(tripId),
    retry: false,
    refetchOnWindowFocus: false,
    refetchInterval: (query) => !query.state.error && query.state.data?.verification.status === "running" ? 800 : false,
  });
}

/** This browser's trips, newest first. The home card and "My trips" share this one query. */
export function useTrips() {
  const { language } = useSettings();
  return useQuery({
    queryKey: [...tripsKey, language],
    queryFn: () => tripGateway.listTrips(language),
    retry: false,
    refetchOnWindowFocus: false,
  });
}
