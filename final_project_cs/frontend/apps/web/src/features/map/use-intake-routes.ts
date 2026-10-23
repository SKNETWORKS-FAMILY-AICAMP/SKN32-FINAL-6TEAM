"use client";

import { useQuery } from "@tanstack/react-query";
import type { Language } from "@/lib/i18n";
import { getIntakeRouteShapes } from "@/lib/live/route-shapes";

export function intakeRouteQuery(intakeId: string, revision: number, language: Language, enabled: boolean) {
  return {
    queryKey: ["intake-route-shapes", intakeId, revision, language],
    queryFn: () => getIntakeRouteShapes(intakeId, language),
    enabled: enabled && Boolean(intakeId),
    retry: false as const,
    refetchOnWindowFocus: false,
    staleTime: 10 * 60_000,
  };
}

export function useIntakeRoutes(intakeId: string, revision: number, language: Language, enabled: boolean) {
  return useQuery(intakeRouteQuery(intakeId, revision, language, enabled));
}
