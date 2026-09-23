"use client";

import { useQuery } from "@tanstack/react-query";
import { tripGateway, tripKey } from "../../lib/gateway";

export { tripKey } from "../../lib/gateway";

export function useTrip(tripId: string) {
  return useQuery({
    queryKey: tripKey(tripId),
    queryFn: () => tripGateway.getTrip(tripId),
    enabled: Boolean(tripId),
    retry: false,
    refetchOnWindowFocus: false,
    refetchInterval: (query) => !query.state.error && query.state.data?.verification.status === "running" ? 800 : false,
  });
}
