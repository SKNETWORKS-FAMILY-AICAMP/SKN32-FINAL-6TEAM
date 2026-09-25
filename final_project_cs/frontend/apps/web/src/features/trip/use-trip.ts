"use client";

import { useQuery } from "@tanstack/react-query";
import { useSettings } from "@/lib/settings";
import { tripGateway, tripKey } from "../../lib/gateway";

export { tripKey } from "../../lib/gateway";

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
