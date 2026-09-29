"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useOnboarding } from "@/features/onboarding/onboarding-state";
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

/** `deleteTrips` for this screen: a deleted trip also stops being the onboarding's active trip. Null where the gateway cannot delete (live). */
export function useDeleteTrips() {
  const queryClient = useQueryClient();
  const { language } = useSettings();
  const [, setOnboarding] = useOnboarding();
  if (!tripGateway.deleteTrip) return null;
  const remove = tripGateway.deleteTrip;
  return (ids: readonly string[]) => deleteTrips(ids, (id) => remove(id, language), queryClient, (deleted) =>
    setOnboarding((current) => current.activeTripId && deleted.includes(current.activeTripId) ? { ...current, activeTripId: null } : current));
}
