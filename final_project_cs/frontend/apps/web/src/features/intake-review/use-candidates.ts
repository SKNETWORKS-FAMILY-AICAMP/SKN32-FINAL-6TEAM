"use client";

import { useQuery, type QueryClient } from "@tanstack/react-query";
import type { Language } from "@/lib/i18n";
import { getCandidates, type CandidateList, type ReviewItem } from "@/lib/live/intake-review";
import { useSettings } from "@/lib/settings";
import { intakeKey } from "./use-intake-stream";

type Target = Pick<ReviewItem, "id" | "source_id" | "index">;

/** The other places for one stop at one revision. A new revision is a new key, so a change never shows an old answer. */
export const candidatesKey = (intakeId: string, language: Language, revision: number, item: Pick<ReviewItem, "id">) =>
  [...intakeKey(intakeId, language), "candidates", revision, item.id] as const;

const FRESH_FOR_MS = 60_000;

/** The other places for a stop, read when asked for (a card is opened, the edit screen is entered). Never throws into the screen. */
export function useCandidates(intakeId: string, item: Target, revision: number, enabled: boolean) {
  const { language } = useSettings();
  return useQuery({
    queryKey: candidatesKey(intakeId, language, revision, item),
    queryFn: () => getCandidates(intakeId, item, revision, language),
    enabled, staleTime: FRESH_FOR_MS, retry: false, refetchOnWindowFocus: false,
  });
}

/** The same read, for an action: uses what a card already fetched, else asks. */
export function fetchCandidates(client: QueryClient, intakeId: string, item: Target, revision: number, language: Language): Promise<CandidateList> {
  return client.fetchQuery({
    queryKey: candidatesKey(intakeId, language, revision, item),
    queryFn: () => getCandidates(intakeId, item, revision, language),
    staleTime: FRESH_FOR_MS,
  });
}
