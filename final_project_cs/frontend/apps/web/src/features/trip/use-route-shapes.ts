"use client";

import { useQuery } from "@tanstack/react-query";
import { getRouteShapes } from "@/lib/live/route-shapes";
import { useSettings } from "@/lib/settings";

/**
 * The route lines of one trip (`GET /v1/web/trips/{id}/route-shapes`), asked once the trip is open and again when the plan moves on (`version`).
 * `data: null` = the server has no such route (an older server) — no lines, and no error to show. An error is a failure to read them.
 */
export function useRouteShapes(tripId: string, version: number | undefined) {
  const { language } = useSettings();
  return useQuery({
    queryKey: ["route-shapes", tripId, version ?? 0],
    queryFn: () => getRouteShapes(tripId, language),
    enabled: Boolean(tripId),
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 10 * 60_000,
  });
}
