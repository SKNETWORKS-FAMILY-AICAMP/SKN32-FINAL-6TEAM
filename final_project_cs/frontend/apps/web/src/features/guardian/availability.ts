"use client";

import { useEffect, useSyncExternalStore } from "react";
import { knownFeatures, loadFeatures, subscribeFeatures } from "@/lib/live/features";
import { useSettings } from "@/lib/settings";

/**
 * `[2026-10-19 사용자 결정 — ST4F-613]` Whether the Course Keeper is shown on the screens before a trip is registered (the plan screen's card, the icon at
 * the top of the reading and the plan check) — the operator's switch, read from the server once per page (`lib/live/features.ts`).
 * null until the answer: the icon waits instead of flashing up and away; the plan screen treats it as before (the card), and the server decides either way.
 */
export function useGuardianShown(): boolean | null {
  const { language } = useSettings();
  const shown = useSyncExternalStore(subscribeFeatures, () => knownFeatures()?.guardian ?? null, () => null);
  useEffect(() => { void loadFeatures(language); }, [language]);
  return shown;
}
